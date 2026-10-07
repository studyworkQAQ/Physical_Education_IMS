# Task 6 任务评审

评审对象：`e5b2b18`（首轮）+ `34691f9`（fix round 1），即 `backend/app/seed/*` 与 `backend/tests/seed/*`。
评审基线：工作树干净，HEAD = `db6d982`。评审全程只读，未改任何受版本控制的文件（末尾附 `git status --short`）。

## 结论

**FAIL** — 数据生成器的「机械正确性」全部通过（可复现、抖动不跨档、清洗一一对账、契约合规、`app/domain` 零污染，我逐条实测复核），但**四类趋势标签的方向是反的**：标为「持续下滑」的 100 名学生本学年总分比上学年**高 53.67 分**、标为「稳步提升」的 125 名学生**低 46.17 分**，而 `trend_label` 被 `fitness.py:471` 明写为「供 Task 8 交叉验证的**真值**」。按 spec §6.3 字面判据实测，`trend_label` 与真实分类的**对角命中率只有 59/500 = 11.8%**，「波动大」75 人里只有 **1 人**满足 VOLATILE 判据。这三条缺陷能通过全部 236 个测试，因为**没有任何一条测试钉住趋势的方向**（`git grep trend_label -- backend/tests` 只命中一处计数断言）。报告 §3 甚至把「持续下滑 +9.03」当作「方向与标签语义一致」的证据写进账本 —— 那个 `+9.03` 恰恰是反证。

---

## 验证过的命令与实测输出

以下每一条都是我在本次评审中亲自执行的，不是我读报告读来的。

### 0. 环境与仓库状态

```
$ cd c:\Users\whwenhao\Desktop\Physical_Education_ims; git status --short; git branch --show-current
（无输出）
feature/plan-01-data-foundation
$ git log --oneline -3
db6d982 docs: Ruling 59-61 更正控制者的三处事实错误
34691f9 fix: 档内抖动与表下溢出使原始值脱离档位端点，上学年按上学年年龄组查表
826f72a docs: Ruling 57/58 收窄档内抖动的适用范围并把表下溢出改为按潜变量排序选取
```

### 1. 测试（两种模式）

```
$ cd backend; python -m pytest -q
236 passed in 21.13s
$ cd backend; python -m pytest -q -W error
236 passed in 12.39s        # 输出洁净，无 warning
```
`tests/seed` 实列 **35** 条测试函数（`test_generate.py` 24 + `test_fitness.py` 11），与报告一致；`tests/seed` 内 `assert` 语句共 **103** 条。

### 2. 可复现性（我自己跑了三次独立 CLI 进程）

```
$ cd backend; python -m app.seed.generate --out-csv $env:TEMP\probeA
$ python -m app.seed.generate --out-csv $env:TEMP\probeB
$ python -m app.seed.generate --seed 1 --out-csv $env:TEMP\probeC

== probeA ==                        == probeB ==                      == probeC (seed=1) ==
body_comp.csv  107559 0ECDDABA7531817A   同 A                        107617 BB36AD613F66A2CF
fitness.csv    244723 35A0E49CB118DB55   同 A                        244430 6EEEC113B6040FAA
survey.csv     275640 DAF36973A0DA49D6   同 A                        276461 B00E217D3743DAD0
```
每个输出目录**恰好 3 个文件**，无 `students.csv`。工作区里既有的 `backend/data/seed/*.csv` 哈希与之**逐一相同**（说明那份落盘文件确实是 HEAD 的产物，不是旧版本遗留）。

### 3. 承重不变式的穷举验证（探针 `probe5.py` / `probe12.py`）

我没有依赖 `test_jitter_never_crosses_a_score_band`（它每档只抽 50 次），而是**穷举**了档内每一个分辨率格点：

```
遍历档数 = 470   独立推导的档内格点总数 = 16365
[1] 档内格点上 score_item != band 的个数 = 0
[2] jitter_raw 输出越出档内格点集的档数 = 0
[3] 无抖动空间却动了的档数 = 0
[4] 小档(<=6 格点)抽样未覆盖满的档数 = 0
[5] 宽档/窄档：pull_up male wide=0 narrow=30；sprint_50m male wide=30 narrow=10、female wide=34 narrow=6；
    其余五组均 wide=38 narrow=2
```
「独立推导」指：方向由「沿 raw 升序看得分是否单调不增」判定（不用 `_band_is_lower_better`），格点集由 `range(centre, min(above))` / `range(max(below)+1, centre+1)` 直接构造（不用 `jitter_raw` 的 `lo/hi`），再逐格调 `score_item` 回验。

RNG 状态级取证（`probe12.py`，用 `bit_generator.state` 的 SHA256 前后比对）：
```
检查了 64 个「无抖动空间」的档，RNG 状态被消耗的 = 0
```

### 4. 端到端交叉验证（我自己重做，探针 `probe6.py`）

```
=== 零注入 → 清洗条目 ===
fitness   行 = 3000  条目 = 0  Counter()
body_comp 行 = 3000  条目 = 0  Counter()
survey    行 = 1000  首行 dimensions 键数 = 5  total = 19.0  raw_answers 键数 = 10
fetch_students(缺失文件) = []
零注入下越出 yaml 区间的单元格 = 0
strength_count min/max = 0.0 57.0   值 <= 0 的条数 = 35   （yaml: min 0 / zero_allowed true / non_positive_is_missing false）

=== 默认注入 → 一一对账 ===
注入痕迹(非 survey) = 1566   清洗条目 = 1566   相等 = True
清洗侧 kind = {missing_dropped 1318, outlier_corrected 173, duplicate_removed 64, unit_normalized 11}
注入侧 kind = {missing 1318, outlier 173, duplicate 70, unit_error 11}；survey 侧 = {duplicate 6}
outlier_corrected 总数 = 173，其中不能归因于 outlier 注入的 = 0
fitness 存活行 = 3000  dropped = 921  corrected = 132 ；body_comp 存活行 = 3000  dropped = 397  corrected = 52
```
即：**干净数据确实产生 0 条清洗条目**；抖动值与表下溢出值**没有任何一个**被记为 `outlier_corrected`；表下溢出的 0–5 次未被误判。

Ruling 44 / 52 取证：
```
被触碰的列 = ['*','body_fat_pct','distance_run_s','height_cm','muscle_mass_kg','sit_and_reach_cm',
              'smi','sprint_50m_s','standing_jump_cm','strength_count','vital_capacity_ml','weight_kg']
含日期列? False   含标识列? False
fitness:   完全相同的多余行 = 35, duplicate 注入 = 35, 相等 = True
body_comp: 完全相同的多余行 = 29, duplicate 注入 = 29, 相等 = True
survey:    完全相同的多余行 =  6, duplicate 注入 =  6, 相等 = True
```

### 5. 落盘 CSV 的契约取证（`probe12.py`，直接读 `backend/data/seed/*.csv`）

```
fitness.csv 行数 = 3035，列 = FITNESS_COLUMNS 的 11 列（逐字相同）
tested_on 非零填充 YYYY-MM-DD 的行数 = 0；含 'T' 的任何单元格 = 0
tested_on 取值 = {2024-09-02, 2024-10-21, 2024-12-16, 2025-09-01, 2025-10-20, 2025-12-15}
batch_key 取值 = {2024-2025|week1, …|week8, …|week16, 2025-2026|week1, …|week8, …|week16}
分辨率：vital_capacity_ml / standing_jump_cm / strength_count 不是 1/1 整数倍的 = 0
        sprint_50m_s / sit_and_reach_cm / distance_run_s 不是 1/10 整数倍的 = 0
        height_cm 不是 1/10 整数倍的 = 11  ← 恰为 11 处 unit_error 注入（厘米→米），非缺陷
survey.csv：JSON 列里 NaN/Infinity 字面量 = 0；2012/2012 可被 json.loads 解析；
            dimensions 键集合唯一；非 ASCII 原样保留（ensure_ascii=False 生效）
```

### 6. 源码级契约合规（`git grep`）

```
$ git grep -n -E 'json\.dumps|default_rng|random|today|now\(|open\(' -- backend/app/seed
app/seed/generate.py:119:    rng = np.random.default_rng(cfg.seed)      ← 全项目唯一一个随机数入口，带种子
app/seed/generate.py:350:        return json.dumps(value, ensure_ascii=False, allow_nan=False)   ← 唯一一处 json.dumps
app/seed/generate.py:326:        with (target / filename).open("w", newline="", encoding="utf-8") ← 唯一一处 open
app/seed/fitness.py:502:            batch_key = base.make_batch_key(plan.academic_year, timepoint) ← 唯一一处 batch_key 构造
（无 import random、无 date.today/dt.date.today/now()、无第二处 json.dumps、无手拼 "|"）
$ git grep -n -E '"\|"|FITNESS_COLUMNS|BODY_COMP_COLUMNS|SURVEY_COLUMNS' -- backend/app/seed
只有 generate.py:322-324 三行引用 base.* 常量，其余全是 docstring 引用；无字面 "|"
$ git diff --stat e5b2b18^..HEAD -- backend/app/domain backend/app/adapters backend/app/pipeline backend/app/refdata.py backend/app/db
（空）← Task 6 两个 commit 对上游模块零改动
$ git grep -n "trend_label" -- backend/app backend/tests
app/seed/fitness.py:362,471,485,594；tests/seed/test_generate.py:256,261   ← 只有 1 处测试，且只数个数
```

### 7. AST 守卫的变异测试（`probe9.py`，把守卫逻辑复制出来打合成违规源码）

```
[OK ] import random                       → 抓到
[OK ] from random import Random           → 抓到
[OK ] np.random.default_rng()   (fitness) → 抓到
[OK ] np.random.default_rng(42) (fitness) → 抓到
[OK ] np.random.default_rng(42) (generate)→ 放过（合法的唯一入口）
[OK ] np.random.seed(0)                   → 抓到
[OK ] dt.date.today()                     → 抓到
[OK ] time.time()                         → 抓到
[!! ] import datetime; datetime.datetime.now()  → 期望抓到，实际放过
[!! ] import datetime; datetime.date.today()    → 放过（守卫集合里只有 "date.today" / "dt.date.today"）
[!! ] np.random.Generator(np.random.PCG64(SeedSequence(0)))  → 放过
```

### 8. CSV 单元格类型扫描（`probe9.py`，numpy 2.4.6）

```
全部 21 个契约列的取值类型 = float / str / dict（Python 原生），numpy 标量 0 个
_cell 产出含 'np.'/'array' 的单元格 = 0
repr(np.float64(1.5)) = np.float64(1.5)      ← 说明这条风险在 numpy 2.x 下是真的，只是当前未触发
```

### 9. 趋势方向（本报告最重要的取证，`probe7.py` / `probe8.py` / `probe10.py`）

```
TREND_PROFILES:
   持续下滑: prev_offset=(4.0, 12.0)   drift_scale=1.0
   波动大:   prev_offset=(-10.0, 10.0) drift_scale=2.5
   稳步提升: prev_offset=(-12.0, -4.0) drift_scale=1.0
   稳定:     prev_offset=(-2.0, 2.0)   drift_scale=0.6

六项总分：本学年 week1 − 上学年 week1（正数 = 本学年更好 = 提升）；零注入、500 人、seed=20250828
  持续下滑: n=100  mean=+53.67  sd=17.21  min=+12.0  max=+100.0   上学年总分 351.20 → 本学年 404.87
  波动大:   n= 75  mean= +4.12  sd=39.90  min=−58.0  max= +70.0
  稳步提升: n=125  mean=−46.17  sd=17.26  min=−96.0  max=  −5.0   上学年总分 459.66 → 本学年 413.50
  稳定:     n=200  mean= −0.40  sd=11.38

逐项（本学年 − 上学年，week1）：
  持续下滑 / vital_capacity +8.79、sprint_50m +9.17、sit_and_reach +9.12、
             standing_jump +8.88、pull_up +8.33、distance_run +9.38      ← 六项全为正
  稳步提升 / vital_capacity −7.53、sprint_50m −7.65、sit_and_reach −8.04、
             standing_jump −7.88、pull_up −6.96、distance_run −8.11      ← 六项全为负

交叉表（行 = 生成器写的 trend_label，列 = 我按 spec §6.3 字面判据 + 计划 Task 8 的求值顺序实现）
label\actual     持续下滑   波动大   稳步提升    稳定   合计   对角命中
持续下滑               0        0      100       0    100        0
波动大                35        1       34       5     75        1
稳步提升             125        0        0       0    125        0
稳定                  70        6       66      58    200       58
对角命中率 = 59/500 = 11.8%
按 spec §6.3 的 DECLINING 判据：230/500 = 46% 被判为持续下滑（配置里只应有 20%）

「波动大」学生 n=75：
  非零变化 ≥3 项且不同号（读法A）: 2/75      ≥3 升且 ≥3 降（读法B）: 0/75
  存在单项 |Δ| ≥ 10: 48/75                   读法A + |Δ|≥10 同时满足: 1/75
  上升项数分布: [(0, 37), (1, 5), (2, 1), (3, 3), (4, 2), (5, 10), (6, 17)]
「稳定」200 人的 DECLINING 触发路径：总分 ≤ −5 → 66 人；仅靠「≥3 项为负」→ 4 人
```

### 10. 旧缺陷量级的复现（`probe3.py` / `probe4.py`）

用 `git show 826f72a:backend/app/seed/fitness.py` 取出修复前的模块、经 `importlib` 顶掉 `sys.modules['app.seed.fitness']` 后重建数据集（**只读，未改工作树**；已核实载入的旧模块 `hasattr(jitter_raw) == False`）：

```
=== 旧代码 (826f72a) ===
  [旧/零注入] 行=396 单元格=2376 不同=334 (0.141) 偏差均值(gp−gc)=+0.873
  [旧/脏注入·排除注入单元格] 行=396 单元格=1866 不同=269 (0.144) 偏差均值=+0.902
  逐项：vital_capacity +1.45(17.7%)、sprint_50m +0.78(15.7%)、pull_up +3.01(51.0%)、
        sit_and_reach 0.00(0%)、standing_jump 0.00(0%)、distance_run 0.00(0%)
  可分辨学生数 = 103 / 132
=== 新代码 (HEAD) ===
  [新/零注入] 行=396 单元格=2376 不同=1213 (0.511) 偏差均值=+2.708   可分辨学生 = 132/132
  [新/脏注入·排除注入] 单元格=1797 不同=928 (0.516)；不去重时 = 946/1827 = 0.518
```

### 11. 其余观测量（`probe1.py` / `probe2.py` / `probe11.py`）

```
人数 500（男 275）；体测 3035（2024-2025 1525 / 2025-2026 1510）；体成分 3029；问卷 1006
教学班 17；选课 1000；注入 1572 = missing 1318 + outlier 173 + duplicate 70 + unit_error 11
corr(endurance,strength) = 0.5211；(endurance,speedflex) = 0.4330；(strength,speedflex) = 0.3418
桶均分 endurance 67.62 / strength 66.51 / speedflex 67.62
潜变量 corr：end/str 0.5727（理论 0.5657）、fit/end 0.8069（理论 0.80）
肺活量 distinct = 1736，官方阈值并集 = 75；非本组阈值占比 96.1%
distance_run 92.9% / sit_and_reach 87.9% / standing_jump 73.7% / sprint_50m 42.2% / strength_count 29.7%
跨线学生 132/500 = 26.400%；年龄分布 18/19/20/21/22 = 132/143/132/80/13
表下溢出：男生 275，标记 28 == int(round(275*0.10))；latent_strength 最大 −1.1447 < 未标记最小 −1.1196
  零注入下被标记者 168 条；strength_count 分布 0→35、1→28、2→28、3→32、4→32、5→13
  按龄组：大一、大二 126 条（0–4）、大三、大四 42 条（0–5，取值 5 只在此组）
  每人最小次数：0→20 人、1→5 人、2→2 人、3→1 人；score 集合 = {10}；学年间趋势集合 = {0.0}
  未标记男生 strength_count 最小 = 7.0；越出 [0, floor_raw) 的条数 = 0
男生力量桶 mean 65.65 / sd 18.43(ddof=1)、18.40(ddof=0) / P25 57.00 / min 15.00；引体向上 10 分者 28/275
memo：调用 2184 次、条目 2184、三元组 1092，两龄组结果相同 = 0、不同 = 1092
floor(target) 就低语义 vs 独立就低推导：24024 组（6项×2性别×2龄组×0.0–100.0 步长 0.1）不一致 = 0
体脂异常率 = 0.3740 (1081/2890)；BMI 得分 <100 比例 = 0.2452 (688/2806)
问卷 total ↔ latent_fitness = 0.3033；total ∈ [5.0, 25.0]，均值 15.88；维度分全是 0.5 的整数倍
行政班 14（35×4 + 36×10）；分层班 提升班 166 / 强化班 167 / 拓展班 167；
  分层班成员 == latent_fitness 三分位 → True（提升班上界 −0.4156 < 拓展班下界 +0.4012）
学号唯一 = True；年级分布 1/2/3/4 = 132/143/132/93；院系 12 个；birth 不同取值 428 个
SeedConfig 字段 = [students, weeks, seed, male_ratio, target_layer_dist, teachers,
  sections_per_teacher, section_size, dirty, trend_mix, intervention_effect, latent_mean,
  jitter_within_band, sub_floor_rate]  →  有 latent_sd 吗? False
cfg.* 消费情况：target_layer_dist → （无：未消费）；body_comp.py / survey.py 从不读 cfg
```

### 12. 工作区 `backend/pe.db` 实况（`probe13.py`）

```
pe.db student 行数 = 596        data/seed/fitness.csv 里的学号数 = 500
CSV 有但 DB 没有 = 0            DB 有但 CSV 没有 = 96
seed=20250828 的 500 人 vs pe.db：不一致的 (学号, 列) 个数 = 0
pe.db 的行与 seed=20250828 完全一致 = 500/500；与 seed=1 完全一致 = 96/500
pe.db enrollment / course_section = 1826 / 17
九张数据表行数 = 全 0
```
（我在评审中跑过 `--seed 1` 的 CLI，已用评审开始前做的字节级备份还原 `pe.db`；还原后文件大小 237568 字节与备份完全一致，即上面这 596/1826 是**评审开始前工作区就有的状态**，不是我造成的。）

---

## 缺陷（按严重度）

### Critical（会让 Task 7–11 出错或产出错误结论）

#### C1. `trend_label` 的方向反了：「持续下滑」的学生在提升，「稳步提升」的学生在下滑

- **位置**：`backend/app/seed/fitness.py:566`（`target -= offsets[student_id][item]`），与 `backend/app/seed/fitness.py:144-146`（`TrendProfile` docstring）、`:153-158`（`TREND_PROFILES` 常量）、`:384`（`_trend_offsets` docstring）三处**自相矛盾**。
- **现象**：三处文档都声明「偏移为正 = 上学年更好 = 下滑」，常量也照这个语义给值（持续下滑 `prev_offset=(4.0, 12.0)` 为正、稳步提升 `(-12.0, -4.0)` 为负）。但 `:566` 用的是**减号**：
  ```python
  target = targets[student_id][item] + drift      # targets = 本学年 week1 的设计得分
  if not plan.is_current:
      target -= offsets[student_id][item]         # 上学年 = 本学年 − 偏移 ← 与 docstring 的「+」相反
  ```
  实测（零注入、500 人、seed=20250828，见「验证过的命令」§9）：
  - `trend_label == "持续下滑"` 的 100 人，本学年六项总分 − 上学年六项总分 = **+53.67**（min +12.0、max +100.0，**100/100 全为正**），六个单项逐一为 +8.33 ~ +9.38；
  - `trend_label == "稳步提升"` 的 125 人 = **−46.17**（min −96.0、max −5.0，**125/125 全为负**），六项逐一为 −6.96 ~ −8.11。
  按 spec §6.3 的字面判据（`持续下滑` = 总分下降 ≥5 **或** ≥3 项单项为负变化；`稳步提升` = 总分上升 ≥5 且无单项下降 ≥5）与计划 Task 8 的求值顺序实现分类器，交叉表是：
  ```
  持续下滑(100) → 100 人全被判为「稳步提升」，0 人命中
  稳步提升(125) → 125 人全被判为「持续下滑」，0 人命中
  对角命中率 59/500 = 11.8%
  ```
- **后果**：
  1. `fitness.py:471` 明写 `trend_label` 是「该生的四类趋势标签**真值**，供 Task 8 交叉验证」。Task 8/9 一旦拿它做交叉验证，会得到 **88.2% 不一致**；最坏的情形是开发者据此去「修」`classify_trend`，把 spec §6.3 的判定逻辑整体反转 —— 那会让 spec §6.1 的规则 **Y4**（`W=0 AND NOT C AND 趋势=持续下滑 → yellow`）在真实数据上反向触发，直接改变分层结果与研究结论。
  2. `cfg.trend_mix` 的语义随之反转：配 `{"持续下滑": 0.20}` 实际得到 20% 的**提升**人群、25% 的下滑人群。spec §10.5「趋势项按四类比例注入」这句话在演示数据里是假的。
  3. 实测 DECLINING 占比 **46%**（230/500）而非配置的 20%，Y4 会在远超预期的样本上触发 —— Task 9 的 20/45/35 校准起点因此是错的（与 M1 叠加）。
  4. 报告 §3（`task-6-report.md:148-153`）把这条缺陷的**证据当成了成功的证据**：表格里写着「持续下滑 … 均分差 **+9.03** … 下降占比 **0.00**」「稳步提升 … **−7.83** … 下降占比 **1.00**」，紧接着一句结论「四类轨迹分离清晰、**方向与标签语义一致**」。控制者把这句和这些数字原样抄进了 `progress.md:598`。「下降占比 0.00」的意思就是「100 个持续下滑的学生里 0 个在下降」。
- **建议**：把 `:566` 改为 `target += offsets[student_id][item]`（这是唯一一处改动，改完代码就与 `:144-146` 的 docstring、`:153-158` 的常量语义、spec §10.5 的「上学年得分 = 本学年得分 − 趋势项（趋势项为负表示下滑）」全部一致）。改完必须重做可复现性取证（三个 CSV 哈希全变）。
- **根因归属**：代码缺陷在实现者一侧（docstring 与代码互斥，实现者自己写的两行相互打脸）。但 spec §10.5 / 计划 Step 4 那句「上学年得分 = 本学年得分 − 趋势项」**从未定义「趋势项」的符号约定**，这是控制者的规格缺口；请一并补上符号定义。
- **置信度**：**高**。方向、量级、逐项一致性、交叉表四条独立证据同向；报告的表格自证。

#### C2. 「波动大」这一类在生成的数据里结构性不可达：75 人中只有 1 人满足 spec §6.3 的 VOLATILE 判据

- **位置**：`backend/app/seed/fitness.py:379-400`（`_trend_offsets` 的「跨六项共享偏移 + 每项小抖动」设计）、`:167`（`ITEM_TREND_JITTER_SD = 1.5`）。
- **现象**：`offsets[sid][item] = shared + N(0, 1.5)`，其中 `shared` 跨六项共享。对「波动大」`shared ~ U(−10, 10)`，逐项抖动 sd 只有 1.5，因此六项**几乎总是同号**。实测 75 名「波动大」学生的上升项数分布是 `[(0, 37), (1, 5), (2, 1), (3, 3), (4, 2), (5, 10), (6, 17)]` —— 37 人六项全降、17 人六项全升。
  spec §6.3 对 `波动大` 的定义是「**≥3 项变化方向不一致** 且 存在单项绝对变化 ≥ 10 分」。实测：
  ```
  非零变化 ≥3 项且不同号（读法A）: 2/75     ≥3 升且 ≥3 降（读法B）: 0/75
  存在单项 |Δ| ≥ 10: 48/75                  两条同时满足: 1/75
  ```
  交叉表里「波动大」75 人被判成：持续下滑 35、波动大 **1**、稳步提升 34、稳定 5。
- **后果**：
  1. Task 8 的 `classify_trend` VOLATILE 分支在**真实生成数据上零覆盖**（75 人里命中 1 人）。计划 Task 8 的 `test_trend_volatile` 是手工构造的黄金用例，会绿；但 Task 10 的端到端与 Task 11 的演示里，这一类基本不存在，spec §6.3 表格的第 2 行在演示数据上无法展示。
  2. `_trend_offsets` 的 docstring（`:386-388`）写着「共享项保证一个人的六个项目朝同一方向变（**Task 8 判趋势靠的正是这种一致性**）」—— 这句话对 DECLINING/IMPROVING 成立，对 VOLATILE **恰好相反**：VOLATILE 的判据就是「方向不一致」。这是又一处「文档说 A、代码做 B」，而且它把缺陷写成了设计意图，所以两轮评审都没人质疑。
  3. `cfg.trend_mix` 里那 15% 的「波动大」配额是空转的：那 75 人实际上是「大幅、同向」的变化，会被判成 DECLINING（35）或 IMPROVING（34），进一步放大 C1/M1 造成的分布失真。
- **建议**：给「波动大」一个**逐项独立、符号强制混合**的偏移模型（例如先按 `drift_scale` 抽每项的幅度，再随机指派符号并保证至少 3 升 3 降），而不是复用 `shared + 小抖动`。同时更正 `_trend_offsets` 的 docstring。改完重做可复现性取证。
- **置信度**：**高**（VOLATILE 判据的两种读法我都算了，结论一致：0–2/75）。唯一的不确定性是 spec §6.3「≥3 项变化方向不一致」的精确读法，见「无法判断的事项」#2 —— 但两种读法都指向同一个结论。

### Major（正确性/可维护性有实质损害，但当前不炸）

#### M1. `prev_offset` 是**逐项**偏移，而 spec §6.3 的阈值是**总分**阈值，两者从未校准 → 「稳定」只有 29% 能被 Task 8 判成稳定

- **位置**：`backend/app/seed/fitness.py:153-158`（四类 `prev_offset` 的量级）与 `:397`（逐项施加）。
- **现象**：`稳定` 的 `prev_offset = (−2.0, 2.0)` 是**每一项**的偏移，六项累加后总分偏移的 sd ≈ 7.8，实测「稳定」200 人的总分差 sd = 11.38。而 spec §6.3 的 DECLINING/IMPROVING 阈值是总分 ±5。实测触发路径：
  ```
  稳定 200 人 → 总分 ≤ −5 的 66 人；仅靠「≥3 项为负」额外触发的 4 人；合计 70 人被判 DECLINING
  稳定 200 人的实际分类：持续下滑 70 / 波动大 6 / 稳步提升 66 / 稳定 58（对角命中 29%）
  ```
- **后果**：全体 500 人按 spec §6.3 判定的实际分布是 **持续下滑 230（46%）/ 波动大 7 / 稳步提升 200 / 稳定 63**，与配置的 100/75/125/200 完全脱节。DECLINING 高达 46% 会让规则 Y4 大面积把「字面绿」升成黄，Task 9 调 `latent_mean` 去命中 20/45/35 时面对的是一个被趋势项严重污染的起点，而 `progress.md:631` 给 Task 9 的派单约束里**完全没有提到这件事**（只提了「μ=0 → 六项均值 67.5」这一条非线性）。
- **建议**：把 `prev_offset` 改成**总分口径**再摊到六项（例如 `per_item = total_offset / 6`），或直接对总分建模后按项拆分；并新增一条断言「四类标签在 spec §6.3 判据下的对角命中率 ≥ 90%」的测试（这条测试同时钉住 C1/C2/M1）。
- **置信度**：**中高**。判定依赖「`classify_trend` 的 `prev_total`/`curr_total` 是六项总分」这一读法 —— 计划 Task 8 的测试用例（`:1092` `prev_total=480, curr_total=444` = 6×80 / 6×74；`:1098` `sum(prev.values()) - sum(curr.values()) == 3`）支持这个读法。若 Task 8/10 实际传入的是 0–100 的加权国标总分，±5 阈值会更难触发，具体比例会变（但 C1/C2 不受影响，因为它们是符号/结构问题不是量级问题）。见「无法判断的事项」#1。

#### M2. `SeedConfig` 缺 `latent_sd` 参数位，计划 Step 3 只实现了一半；`progress.md:619` 的接受理由是**控制者的事实错误**

- **位置**：`backend/app/seed/config.py:188`（只有 `latent_mean: float = 0.0`）、`backend/app/seed/fitness.py:189`（`rng.normal(cfg.latent_mean, 1.0, total)` —— σ 硬编码为字面量 `1.0`）。
- **现象**：计划 Step 3（`Document/…实施计划01….md:902`）明写「本 Task 只暴露 `latent_mean` / **`latent_sd`** 参数位并保证生成正确」。实测：
  ```
  SeedConfig 字段 = [..., intervention_effect, latent_mean, jitter_within_band, sub_floor_rate]
  有 latent_sd 吗? False
  $ git grep -n "latent_sd" -- backend      → （空）
  ```
  而 `progress.md:619` 写「关切 ④：Step 3 的『二分法调 μ』未实现，只开 **`latent_mean`/`latent_sd`** 参数位……正确」——`latent_sd` 从来没被开出来。实现者报告 `task-6-report.md:266` 说的是实话（「落地方式：`SeedConfig.latent_mean: float = 0.0`」，只提一个），是控制者在接受时补上了一个不存在的字段。
- **后果**：`progress.md:680` 把「随机流的形状参数」列为三个（`MEASURE_DECIMALS` / `sub_floor_rate` / `jitter_within_band`），漏了 σ。Task 9 若发现只调 μ 无法命中 20/45/35（红层依赖低尾的**离散度**，不只是位置），就必须改 `fitness.py:189` 的源码而不是改配置 —— 而改源码会同时改变随机流形状，触发一次未被预告的全量字节变更。
- **建议**：加 `latent_sd: float = 1.0` 字段，`:189` 改为 `rng.normal(cfg.latent_mean, cfg.latent_sd, total)`；更正 `progress.md:619`，并把 σ 加进 `:680` 的形状参数清单。
- **置信度**：**高**（`dataclasses.fields` 与 `git grep` 双重取证）。

#### M3. 报告 F1.2 的「1213 / 2376 = 51.1%」不是旧缺陷的量级，而是**修复后**数据在**反方向**上的度量；旧缺陷的真实量级是 **334 / 2376 = 14.1%**（相差 3.6 倍）。该错误数字已写进计划正文。

- **位置**：`task-6-report.md:400`、并被抄进 `Document/2026-09-28-实施计划01-数据基座与分层引擎.md:887`（「实测 2376 个上学年单元格里有 **1213** 个两张表给出不同得分，每项趋势被系统性低估约 0.83 分」）。
- **现象**：我用 `git show 826f72a:…fitness.py` + `importlib` 重建了修复前的数据集（只读，未改工作树），在同一份评分表上复算（见「验证过的命令」§10）：
  | 实验 | 单元格 | 两表不同 | 可分辨学生 |
  | --- | --- | --- | --- |
  | **旧代码**（缺陷现场）零注入 | 2376 | **334 = 14.1%** | **103 / 132** |
  | 旧代码 脏注入·排除注入格 | 1866 | 269 = 14.4% | — |
  | **新代码**（已修）零注入 | 2376 | **1213 = 51.1%** | 132 / 132 |
  | 新代码 脏注入·排除注入格 | 1827（不去重） | 946 = 51.8% | — |

  两个方向的差别是真实的、可解释的：旧代码的原始值是**高龄组表的端点**，拿到低龄组表上重查时，只有「两表阈值差 ≥ 档距」的项才会掉档（引体向上差 1 次 = 档距 1 次 → 精确掉档，所以它偏差最大；坐位体前屈差 0.5 cm < 档距 1.0 cm → 恒不掉档）。新代码的原始值是**低龄组表的端点**，拿到高龄组表上重查则普遍掉档。报告把后者的计数放进了标题为「**缺陷的量级**」的表格里。
  同一张表里另一行「旧代码下管道按上学年龄组重算的偏差 均值 **+0.827** 分/项（**1827** 个未注入单元格）」又是**旧方向**的实验（我复算：旧代码零注入 +0.873 / 2376 格，旧代码排除注入 +0.902 / 1866 格），而 1827 这个分母只在**新代码**的脏数据集上出现。也就是说这张四行表混用了两个互不相容的实验口径。
  逐项偏差我复算为 引体向上 +3.01(51.0%) / 肺活量 +1.45(17.7%) / 50米 +0.78(15.7%) / 其余三项 0.00(0%)，与报告的 +2.72(46.3%) / +1.40(17.0%) / +0.82(16.5%) / 0.00(0%) **模式完全一致、数值略偏**（差异可由报告是在「已有抖动+表下溢出但龄组仍是旧的」中间态上测得解释；表下溢出会把约 22 个引体向上单元格强制变成 0 偏差）。这一行我判定为**可接受**。
- **后果**：Ruling 56 的影响面被高估 **3.6 倍**，而这个数字已经进了计划正文，Task 9 的派单会引用它。这与 Ruling 61 修掉的「45% vs 26.4%」是**同一类错误**（把一个方向的度量当成另一个方向的量级），只是这次藏在分子里、而且控制者已经为上一次错误专门写过一条裁定。附带：「132 名跨线学生人人至少有一格能被分辨」在旧代码下是 **103/132**，不是 132/132。
- **建议**：更正 `task-6-report.md:400` 与计划 `:887`，把两个实验分开写清（「旧缺陷影响 334/2376 = 14.1% 的单元格、103/132 名学生；修复后测试的可分辨性是 1213/2376 = 51.1%、132/132」）。**Ruling 56 本身的裁定是对的，缺陷是真的、也真该修** —— 错的只是量级数字。
- **置信度**：**高**（我完整重放了旧代码，且新旧两个方向都能精确复现报告里各自那一半数字，这本身就证明了两组数字来自两个不同实验）。

#### M4. 工作区的 `backend/pe.db` 与 `backend/data/seed/*.csv` 描述的不是同一批人；`progress.md:628` 记录的「500/17/1000 不翻倍」与实况不符

- **位置**：`backend/app/seed/generate.py:469-503`（`main()` 无 `--reset`、无 `--db`，一律写 `DEFAULT_DB_URL`；`student` 表无 seed 溯源列）。
- **现象**：实测（`probe13.py`，且我跑 CLI 前已做字节级备份、评审后已还原，所以这是**评审开始前的工作区状态**）：
  ```
  pe.db student = 596    enrollment = 1826    course_section = 17    九张数据表 = 全 0
  data/seed/fitness.csv 的学号数 = 500；DB 有但 CSV 没有 = 96
  pe.db 的行与 seed=20250828 完全一致 = 500/500；与 seed=1 完全一致 = 96/500
  ```
  即：有人（实现者或控制者做可复现性取证时）用 `--seed 1` 跑过 CLI，`repo.upsert` 按 `student_no` 幂等更新，于是 500 个 seed=20250828 的学生被原样保留、外加 96 个只属于 seed=1 的孤儿学生，且这 96 人被编进了同一批 course_section（1826 = 1000 + 826）。`progress.md:628` 的延后 Minor 写的是「实现者实际跑过 CLI 验证幂等：**500/17/1000** 不翻倍」，与实况不符。
- **后果**：Task 10 直接消费 `backend/pe.db`。届时队列分母是 596 而 CSV 里的测量数据只覆盖 500 人，96 名学生永远不会有体测记录；百分位快照（Task 7）与分层（Task 9）的分母口径会被无声污染，而 `daily_sync_run` 的计数不会报错 —— 这正是本项目最忌讳的「静默不一致」。此外 CLI 缺省「既写盘也入库」（计划确实这么要求），意味着**任何人为了做哈希取证而跑一次 `--seed X`，就会永久污染 pe.db**，而 M4 的成因恰恰就是取证本身。
- **建议**：两条都要做 —— (a) Task 10 派单前删除 `backend/pe.db` 并用缺省 seed 重建一次；(b) 给 CLI 加 `--reset`（写库前按自然键清空五张组织结构表）或 `--db URL`，并把「跑非缺省 seed 会累积人群」写进 `main()` 的 docstring。`progress.md:628` 同步更正为 596/17/1826。
- **置信度**：**高**（直接查库）。

#### M5. 没有任何测试钉住趋势的**方向**，这是 C1/C2/M1 能活过两轮评审的直接原因

- **位置**：`backend/tests/seed/test_generate.py:256-268`（`test_trend_labels_are_injected_at_configured_ratios`，只断言四类计数 == `round(500*ratio)`）。
- **现象**：取证命令与输出（`probe10.py`）：
  ```
  $ git grep -n -E "trend_label|持续下滑|稳步提升|波动大|TREND_PROFILES|prev_offset|_trend_offsets" -- backend/tests
  backend/tests/seed/test_generate.py:256:def test_trend_labels_are_injected_at_configured_ratios():
  backend/tests/seed/test_generate.py:261:        per_student.setdefault(...).add(r["trend_label"])
  ```
  全仓测试里只有这一处提到趋势，而它只数个数。`tests/seed` 内 `assert x in (A, B)` 式的两可断言 **0 处**（`git grep -n -E "assert .+ (in|==) *\(" -- backend/tests/seed` 为空），所以问题不是断言太松，而是**这条性质根本没有断言**。
- **具体缺失的输入**（不是「建议加更多测试」，是这一条）：取任一 `trend_label == "持续下滑"` 的学生，断言其**本学年 week1 的六项总分 < 上学年 week1 的六项总分**；对称地断言「稳步提升」为 `>`；再断言「波动大」的学生里至少有一个满足 spec §6.3 的「≥3 项方向不一致且存在单项 |Δ| ≥ 10」。实测这三条在当前代码下分别是 0/100、0/125、1/75 通过。
- **后果**：C1/C2/M1 三条缺陷全部在 236 passed 之下。这也说明报告 §3 那张「四类趋势标签的实际轨迹」表是**手工统计**而非测试断言 —— 手工统计出来的数字（+9.03）被人读成了「方向一致」，而如果有测试，它会当场红。
- **建议**：随 C1/C2/M1 的修复一并加上，放在 `tests/seed/test_fitness.py`（它已经是「单条记录怎么算出来」的归属文件）。
- **置信度**：**高**。

### Minor（延后到终审）

#### m1. AST 守卫漏掉无别名的 `datetime` 写法与 `Generator(PCG64(...))`

- **位置**：`backend/tests/seed/test_generate.py:485-506`。
- **现象**：变异测试实测（§7）—— `import datetime; datetime.datetime.now()` 与 `import datetime; datetime.date.today()` 都**不被抓**（`clock_calls` 里只有 `"datetime.now"`/`"date.today"`/`"dt.date.today"` 等 7 个精确串，`ast.unparse` 对无别名写法给出的是 `"datetime.datetime.now"` / `"datetime.date.today"`）；`np.random.Generator(np.random.PCG64(np.random.SeedSequence(0)))` 也不被抓。抓到的 8 种写法（`import random`、`from random import`、非 generate.py 的 `default_rng`、generate.py 内无参 `default_rng`、`np.random.seed`、`dt.date.today`、`dt.datetime.now`、`time.time`）都对。
- **后果**：低 —— 全仓统一用 `import datetime as dt`，且 `default_rng` 那条覆盖了最常见的隐藏随机源。但守卫的价值就在于「结构性不可达」，留一个精确串匹配的白名单等于留了一条绕过路径。
- **建议**：把时钟判定改成「解析 `ast.unparse(node.func)` 后取**末段属性名** ∈ `{today, now, utcnow, time, monotonic, perf_counter}`」，随机源判定加 `Generator` / `SeedSequence` / `PCG64` / `MT19937` / `spawn` / `fork`。
- **置信度**：高。

#### m2. `_cell` 对 numpy 标量会写出 `np.float64(1.5)` 这样的坏单元格

- **位置**：`backend/app/seed/generate.py:351-356`（`if isinstance(value, float): … return repr(value)`）。
- **现象**：`np.float64` 是 Python `float` 的子类，故会进这个分支；numpy 2.4.6 下实测 `repr(np.float64(1.5)) == 'np.float64(1.5)'`。当前**未触发**：21 个契约列 × 全量记录的类型扫描全是 Python 原生 `float`/`str`/`dict`，0 个 numpy 标量（§8）。
- **后果**：将来任何一处漏掉 `float(...)` 包装（例如把 `round(np.clip(...), 1)` 直接塞进记录），CSV 里就会出现 `np.float64(17.3)`，适配器 `float()` 解析会抛 `ValueError` 并中断整批抽取 —— 好在是响亮失败而不是静默。
- **建议**：`return repr(float(value))`（一个词的改动，把隐患变成结构性不可达）。
- **置信度**：高（现状未触发，属防御性；我把它列出来是因为 numpy 2.x 的 `repr` 变更正是这类代码的经典杀手）。

#### m3. `fitness.py:28` 的模块 docstring 与事实不符

- **位置**：`backend/app/seed/fitness.py:28-30`：「**本模块是 ``app.seed`` 里唯一会碰磁盘的地方**，而且只经 `app.refdata.standard()` 这个受管加载器读国标评分表」。
- **现象**：`fitness.py` 自己一个文件都不 open；真正碰磁盘的是 `generate.py:326`（写三个 CSV）与 `generate.py:102`（经 `load_ranges` 读 `indicator_ranges.yaml`）。取证：`git grep -n -E "open\(|read_text|read_csv" -- backend/app/seed` 只命中 `generate.py:326`。
- **后果**：低，但它是本项目已多次出现的「文档说 A、代码做 B」模式的又一例，而且这句话的字面意思（「唯一」）恰好是错的。
- **建议**：改成「本模块只经 `app.refdata.standard()` 这个受管加载器读国标评分表，自己不 open 任何文件；`app.seed` 里的写盘只在 `generate.write_csv`」。
- **置信度**：高。

#### m4. 潜变量残差按「标准差」读，与计划 Step 3 的 `N(0, 0.6)` 惯用记法不一致，且计划正文未同步更正

- **位置**：`backend/app/seed/fitness.py:70-77`（`LATENT_LOADINGS` 与其 docstring）；计划 `Document/…实施计划01….md:872-874` 仍写 `N(0, 0.6)`。
- **现象**：统计学惯例 `N(μ, σ²)` 的第二个参数是**方差**；实现按**标准差**读（`rng.normal(0.0, sd, total)`，`sd=0.6`）。实现者的算术自证是对的：按 sd 读理论 corr(endurance, strength) = 0.56/sqrt(1.00×0.98) = **0.566**（实测潜变量 corr **0.5727**），按方差读会掉到 **0.461** —— 叠上逐项噪声与档位离散化后确实会贴近 `> 0.4` 那条断言。处置合理，docstring 也写清了理由。
- **后果**：低。但计划正文没改，Task 9+ 的读者拿计划对代码会对不上；而且如果哪天有人「照计划修正」成方差读法，耐力/力量得分相关会从 0.5211 掉到 0.4 附近，`test_indicator_correlation_is_realistic` 变成一个换种子就可能翻车的定时炸弹。
- **建议**：把计划 Step 3 的三行改成 `N(0, 0.6²)` 或明写「括号内是标准差」。
- **置信度**：高。

#### m5. `progress.md` 里若干 round-1 观测量在 fix round 1 后已过期，但控制者只作废了一部分

- **现象**：`progress.md:649` 明确作废了「`E44FC324…`/`95657898…`/`04D03267…` 与 0.533、67.4、1554」，但 `:598` 里同一段的其余数字没作废，实测全部已变（原因是抖动/表下溢出平移了随机流，而 `body_comp`/`survey` 在 `fitness` 之后消费同一条流）：
  | progress.md 记的 | 实测（HEAD） |
  | --- | --- |
  | 体脂异常率 0.360 | **0.3740** (1081/2890) |
  | 问卷总分↔latent_fitness 0.295 | **0.3033** |
  | BMI 异常率 0.247 | **0.2452** (688/2806) |
- **后果**：低（三条都还在断言区间内），但 Task 9/10 的派单若引用它们会与实况不符 —— 与 M3 同源，都是「fix round 之后旧数字没清干净」。
- **建议**：`progress.md:598` 整段标注为 round-1 快照并补一行 round-1 之后的实测值。
- **置信度**：高。

#### m6. `cfg.target_layer_dist` 是死配置；`make_body_comp` / `make_survey` 的 `cfg` 参数从未被读取

- **位置**：`backend/app/seed/config.py:155-157`；`backend/app/seed/body_comp.py:56-61`、`backend/app/seed/survey.py:71-76`。
- **现象**：实测 `cfg.*` 消费图（§11）—— `target_layer_dist` **零消费**；`body_comp.py` 与 `survey.py` 从不读 `cfg`（体脂率基准、SMI 基准、李克特权重全是模块级常量）。`target_layer_dist` 是计划 Interfaces 清单要求的字段、且 Step 3 明写二分法归 Task 9，属有意留位；`cfg` 参数也是计划钉死的签名。
- **后果**：低。但 `target_layer_dist` 没有任何注释或测试指出「它现在不影响任何输出」，Task 9 的实现者很可能先改它、发现数据没变、再回头翻代码。同理，Task 9 若要调体脂异常率（0.3740 已在 0.20–0.50 的上半区）必须改 `body_comp.py` 源码。
- **建议**：在 `target_layer_dist` 的注释里加一句「本计划内零消费，由 Task 9 的二分法接线」；在 `make_body_comp` / `make_survey` 的 docstring 里写明「`cfg` 目前未被消费，保留是为接口一致性」。
- **置信度**：高。

#### m7. `duplicate` 注入把副本追加到文件**末尾**，而不是紧邻原行

- **位置**：`backend/app/seed/generate.py:204`（`output.extend(copies)`）。
- **现象**：三类源的重复行都堆在 CSV 尾部（实测 fitness 35 条、body_comp 29 条、survey 6 条）。功能上无碍：`_dedup` 按输入顺序保留后者、两行逐字相同（Ruling 52 已验证），存活行还就地替换回原位置。
- **后果**：低。但 `_mark` 的 reason 文案声称模拟的是「增量水位线未推进或源系统重传」，那种场景下重复行通常紧邻原行或落在下一个增量批次里；全堆在尾部让演示数据的故事与形状不一致。
- **建议**：不改也行；若要改，把副本插到原行之后（`output.insert(len(output), …)` → 改为在循环内直接 `output.append(dict(row))`）。注意这会改变 CSV 字节，需重做哈希取证。
- **置信度**：高（现象），中（是否值得改）。

#### m8. `test_inject_dirty_leaves_clean_records_untouched_when_all_rates_are_zero` 的末尾挂了一条与测试名无关的断言

- **位置**：`backend/tests/seed/test_generate.py:524-525`（`sections = make_sections(...)` + `assert set(sections) == {"course_sections", "enrollments"}`）。
- **现象**：测试名声称量的是「注入比例为 0 时一行不改」，最后两行却在检查 `make_sections` 的返回键集合，且这条性质已由 `test_two_grouping_modes_coexist` / `test_every_student_enrolled_in_both_grouping_modes` 覆盖。
- **后果**：极低（不是空转，只是归属错位，会让失败定位多绕一步）。
- **建议**：删掉，或挪进一条专门检查 `make_sections` 返回契约的测试。
- **置信度**：高。

---

## 报告数字复核表

| # | 报告/账本声称 | 我的实测 | 一致 |
| --- | --- | --- | --- |
| 1 | `pytest -q` → 236 passed | 236 passed in 21.13s | ✅ |
| 2 | `pytest -q -W error` → 236 passed、洁净 | 236 passed in 12.39s、无 warning | ✅ |
| 3 | `tests/seed` 35 passed（24 + 11） | 24 + 11 = 35 条测试函数 | ✅ |
| 4 | fitness.csv SHA256 前 16 = `35A0E49CB118DB55`，两次独立进程相同 | 相同（probeA == probeB == 工作区文件） | ✅ |
| 5 | body_comp.csv = `0ECDDABA7531817A` | 相同 | ✅ |
| 6 | survey.csv = `DAF36973A0DA49D6` | 相同 | ✅ |
| 7 | seed=1 → `6EEEC113B6040FAA` / `BB36AD613F66A2CF` / `B00E217D3743DAD0`，三个全不同 | 逐一相同 | ✅ |
| 8 | 字节数 244723 / 107559 / 275640 | 相同 | ✅ |
| 9 | 输出目录恰好三个文件、无 `students.csv` | 相同 | ✅ |
| 10 | 人数 500（男 275 / 女 225，0.550） | 相同 | ✅ |
| 11 | 体测 3035 条（2024-2025 1525、2025-2026 1510） | 相同 | ✅ |
| 12 | 体成分 3029 条、问卷 1006 份 | 相同 | ✅ |
| 13 | 教学班 17 个、选课关系 1000 条 | 相同 | ✅ |
| 14 | 注入 1572 处（missing 1318、outlier 173、duplicate 70、unit_error 11） | 相同 | ✅ |
| 15 | 耐力/力量相关 **0.5211** | 0.5211（我在 505 行 w1 上算，含 5 条 duplicate 副本；报告写 n=500 —— 两种口径同值） | ✅ |
| 16 | 耐力/速度柔韧 0.4330、力量/速度柔韧 0.3418 | 相同 | ✅ |
| 17 | 桶均分 67.62 / **66.51** / 67.62 | 相同 | ✅ |
| 18 | 肺活量 **1736** 个不同取值、官方阈值 **75** 个 | 相同 | ✅ |
| 19 | 非本组阈值占比 96.1% / 92.9% / 87.9% / 73.7% / **42.2%** / 29.7% | 六项逐一相同 | ✅ |
| 20 | 亚分辨率值（6.73 s 这种）一个都没生成 | 落盘 CSV 里 sprint/sit_and_reach/distance_run 不是 1/10 整数倍的 = **0** | ✅ |
| 21 | 跨线学生 **132/500 = 26.4%**；年龄分布 132/143/132/80/13 | 相同 | ✅ |
| 22 | 受影响的上学年记录 **396** 条 | 数据集里实际是 **402 行**（含 6 条 duplicate 副本）；396 是 132×3 的算术值 | ⚠️ 口径 |
| 23 | 两表给出不同得分的单元格 **1213 / 2376 = 51.1%** | 旧代码方向 **334 / 2376 = 14.1%**；1213/2376 是**修复后**数据在反方向的度量 | ❌ **严重** |
| 24 | 132 名跨线学生**人人**至少有一格能被分辨 | 旧代码方向 **103/132**；新代码方向 132/132 | ❌ |
| 25 | 偏差均值 **+0.827** 分/项（1827 个未注入单元格） | 旧代码零注入 **+0.873**（2376 格）/ 旧代码排除注入 **+0.902**（1866 格）；1827 这个分母只在新代码数据上出现 | ⚠️ 量级对、口径混 |
| 26 | 逐项偏差 引体 +2.72(46.3%)、肺活量 +1.40(17.0%)、50米 +0.82(16.5%)、其余三项 0.00(0%) | 引体 +3.01(51.0%)、肺活量 +1.45(17.7%)、50米 +0.78(15.7%)、其余三项 0.00(0%) | ⚠️ 模式一致、数值略偏 |
| 27 | 被标记男生 **28** == `int(round(275*0.10))` | 相同 | ✅ |
| 28 | latent_strength 最大 **−1.1447** < 未标记最小 **−1.1196** | 相同（严格不等成立，无一处平手） | ✅ |
| 29 | 被标记者记录数 **168**（28×6） | 零注入下 168；默认注入的数据集里是 **172**（含 4 条 duplicate 副本） | ✅（需注明口径） |
| 30 | `strength_count` 分布 0/1/2/3/4 = **35/28/28/32/32**，另 13 条取值 5 | 逐一相同 | ✅ |
| 31 | 按龄组：大一二 126 条（0–4）、大三四 42 条（0–5，取值 5 只在此组） | 相同 | ✅ |
| 32 | 每人最小次数 0→20 人、1→5 人、2→2 人、3→1 人 | 相同 | ✅ |
| 33 | 被标记者 score 集合 = {10}；该项学年间趋势 28/28 = 0 | 相同（趋势集合 = `{0.0}`） | ✅ |
| 34 | 未标记男生 `strength_count` 最小 7.0 | 相同 | ✅ |
| 35 | 男生力量桶 65.65 / sd 18.40 / P25 57.00 / min 15.00；引体向上 10 分者 28/275 | 65.65 / 18.43(ddof=1)、18.40(ddof=0) / 57.00 / 15.00 / 28 | ✅ |
| 36 | memo 1092 组全不同、0 组相同、条目 2184 = 1092×2 | 相同 | ✅ |
| 37 | 四类趋势标签精确 100/75/125/200 | 计数相同；**语义反了**（见 C1） | ⚠️ 计数✅/语义❌ |
| 38 | 「持续下滑 +9.03、稳步提升 −7.83、稳定 −0.06、波动大 sd 6.67」且「**方向与标签语义一致**」 | 逐项均分差 +8.33~+9.38 / −6.96~−8.11 / −0.067 / sd 6.65 —— **数字全对，但结论是错的**：+9.03 意味着「持续下滑」的六项在**上升** | ❌ **结论错** |
| 39 | 行政班 14（35×4 + 36×10）、分层班 166/167/167、成员 == latent_fitness 三分位 | 相同 | ✅ |
| 40 | 体脂异常率 0.360（round 1，未作废） | 现 **0.3740** | ❌ 过期 |
| 41 | 问卷↔latent_fitness 0.295（round 1，未作废） | 现 **0.3033** | ❌ 过期 |
| 42 | BMI 异常率 0.247（round 1，未作废） | 现 **0.2452** | ❌ 过期 |
| 43 | 「抖动与溢出都不产生新的清洗条目」「干净数据 0 条清洗条目」 | 零注入 → fitness/body_comp 各 3000 行、**0 条**条目；173 条 `outlier_corrected` **全部**可归因于注入 | ✅ |
| 44 | 1566 处非问卷注入与清洗条目按 `(source, kind, field)` 一一对应 | 1566 == 1566，Counter 完全相等 | ✅ |
| 45 | `pe.db`「500/17/1000 不翻倍、九张数据表全 0 行」 | **596/17/1826**，九张数据表全 0 | ❌ 人数与选课数不符 |
| 46 | `SeedConfig` 开了 `latent_mean`/`latent_sd` 两个参数位（progress.md:619） | 只有 `latent_mean`；`latent_sd` 在 `backend/` 内零命中 | ❌ |
| 47 | `jitter_raw` 无抖动空间时不消耗随机数 | 64 个无空间档，RNG `bit_generator.state` 的 SHA256 前后 **0 处变化** | ✅ |
| 48 | 男生引体向上 15 档 × 2 龄组恒不抖动 | wide=0 / narrow=30 | ✅ |
| 49 | 50 米跑只有最高 4 档无抖动空间 | 实测男 narrow=10（每组 5：100/95/90/85 四个 0.1 档距 + 顶档无更好侧）、女 narrow=6（每组 3） | ⚠️ 措辞略偏（每组是 5 不是 4），结论不变 |
| 50 | `floor(target)` 的取整与 `raw_from_score` 的就低语义等价 | 24024 组（6项×2性别×2龄组×0.0–100.0 步长 0.1）与独立就低推导 **0 处不一致** | ✅ |

**对不上的项汇总**：#23、#24（M3，严重）、#38（C1，结论错）、#45（M4）、#46（M2）、#40/#41/#42（m5，过期未作废）；#22/#25/#26/#29/#37/#49 是口径或措辞问题，数字本身可解释。

**关于「1092 组全不同」这个实验证明了什么**（评审重点 B 最后一条）：它证明的是**memo 键里的 `age_group` 是承重的** —— 若把它从键里去掉，1092 个 `(item, score, sex)` 三元组会 **100% 串味**（0 组在两个龄组下给出相同结果），从而 `test_generated_raw_values_roundtrip_through_the_official_table` 与 `test_previous_year_records_use_the_previous_year_age_group` 会立刻炸。它**不**证明当前 memo 是正确的（那由 roundtrip 测试证明）。这是一个「变异敏感性」论证，作为对简报「别假设」要求的回应是恰当的、有意义的，我认可。另外我独立补做了它没做的那一半：`math.floor(target)` 后就低取档 ≡ 独立推导的「不超过 target 的最大官方档」，24024 组 0 处不一致 —— 这一条报告只是论证（「国标档位分全是整数」），我把它变成了穷举事实。

---

## 值得肯定的地方（只写我验证过的）

1. **可复现性是真的**：我亲自跑了三次独立 CLI 进程，三个 CSV 的 SHA256 前 16 位与报告**逐一相同**（含 `seed=1` 的三个），每个目录恰好 3 个文件、无 `students.csv`；`app/seed` 内只有一个带种子的 `default_rng`、零处 `import random`、零处时钟调用（`git grep` 取证）。
2. **档内抖动的承重不变式在穷举下成立**：24 组 × 470 个官方档 × **16365 个分辨率格点**，`score_item` 跨档 **0** 处；`jitter_raw` 的输出 **0** 处越出档内格点集；64 个「无空间」档的 RNG 状态 **0** 处被消耗。这比测试里「每档抽 50 次」强得多，而它撑住了。`_room_in_units` 确实是从 `segment_thresholds` + `score_item` 独立推导的（我的独立推导给出完全相同的 wide/narrow 分类）。
3. **端到端一一对账不是自证**：零注入 → fitness/body_comp 各 3000 行、**0 条**清洗条目（说明生成器的本底分布全部落在 `indicator_ranges.yaml` 内部，表下溢出的 0–5 次也正确落在 `strength_count` 的 `min:0 / zero_allowed:true` 之内）；默认注入 → 1566 条非问卷痕迹与 1566 条清洗条目按 `(source, kind, field)` **Counter 完全相等**，且 173 条 `outlier_corrected` **全部**可归因于注入（0 条来自抖动）。
4. **契约合规无可挑剔**：`app/seed` 内只有一个 `json.dumps`（带 `ensure_ascii=False, allow_nan=False`）、一个 `make_batch_key` 调用点、零处手抄列序、零处字面 `"|"`；落盘 CSV 无一处 `T` 后缀、无一处 `NaN`/`Infinity` 字面量、六列测量值全部是 `10^-MEASURE_DECIMALS` 的整数倍（`height_cm` 那 11 处例外恰为 11 个 `unit_error` 注入）；Ruling 44 的白名单实测正好是那 11 个测量列 + `*`，日期列与标识列 **0** 命中；Ruling 52 的逐字复制在三类源上全部成立（35/29/6）。
5. **`app/domain` / `app/adapters` / `app/pipeline` / `app/refdata.py` / `app/db` 在 Task 6 的两个 commit 内零改动**（`git diff --stat e5b2b18^..HEAD` 取证），架构守卫仍全绿；Ruling 58 的单调性在最严形式下成立（−1.1447 < −1.1196，无平手）；`make_sections` 的分层班成员实测**恰好等于** `latent_fitness` 升序三分位。

---

## 无法判断的事项

1. **`classify_trend` 的 `prev_total`/`curr_total` 到底是「六项总分」还是「加权国标总分」**。仓库里还没有权重常量（`git grep -E "WEIGHT|national_total" -- backend/app` 只命中 `weight_kg` 与 Task 8 的类型声明）。我用「六项总分」算出了 M1 与交叉表，依据是计划 Task 8 自己的测试用例（`:1092` `prev_total=480, curr_total=444` = 6×80/6×74；`:1098` `sum(prev.values()) - sum(curr.values()) == 3`）。若 Task 8/10 实际传 0–100 的加权总分，M1 的具体比例会变（±5 阈值相对更难触发，「稳定」的泄漏会减少、但「持续下滑/稳步提升」的 ±24~±72 总分偏移仍会远超阈值）；**C1 与 C2 完全不受影响**，因为它们是符号与结构问题，不是量级问题。请控制者在 Task 8 派单时钉死这个口径。
2. **spec §6.3「≥3 项变化方向不一致」的精确判据**。计划 Task 8 的 `test_trend_volatile` 用例是 `deltas = (+15, −15, +13, −13, 0, 0)` 且注释写「4 项方向不一致」，据此我采用「非零变化 ≥3 项且不同号」（读法A）；另一种读法是「≥3 升且 ≥3 降」（读法B）。两种我都算了：75 名「波动大」学生里读法A 命中 2 人、读法B 命中 0 人，**C2 的结论不变**。但 Task 8 的实现者需要一条裁定。
3. **Step 2「运行测试确认失败」与 F5.4 的 TDD RED 历史**无法在当前工作树上复现 —— 我没有 checkout 到 `e5b2b18^` 或 `826f72a` 去跑测试（那会改工作树）。我只能核对报告文本，无法独立重放那条 `ImportError: cannot import name 'MEASURE_DECIMALS'` 与那条 `assert {10.0, 10.1} == {10.1}` 的 RED。我用 `git show` + `importlib` 重建旧模块的做法是只读的，但它验的是 Ruling 56 的量级，不是 TDD 顺序。
4. **`national_standard_2014.csv` 的官方数据正确性**属 Task 2 评审范围。我把它当作查表 oracle 使用（470 个档、16365 个格点的穷举都以它为准），未复核任何一格官方阈值的真伪。若那 3 个 0.1 宽舍入缝或那一格 76/78 分争议最终被改，我的穷举结论需要重跑（脚本已在本文档里，重跑成本低）。
5. **Task 9 能否只靠调 `latent_mean` 命中 20/45/35**。我没有分层引擎，无法预判。但可以确定的是：M1 造成的 **46% DECLINING** 会让规则 Y4 在远超预期的样本上触发（Y4 = `W=0 AND NOT C AND DECLINING → yellow`），这一定会显著抬高黄层、压低绿层；`progress.md:631` 给 Task 9 的前向约束里只写了「μ=0 → 六项均值 67.5」这一条非线性，**没有提到趋势项的污染**。建议把 C1/C2/M1 修完再派 Task 9，否则 Task 9 的二分会在错误的数据上收敛。
6. **报告 §8 提到的「写盘事故」是否复发**。我只核对了 `task-6-report.md` 的当前字节数（66913）与 `## Fix Round 1` 出现在第 336 行（与 `progress.md:674` 一致），未逐节比对报告的历史完整性 —— 那超出本次评审范围。

---

## 附：控制者裁定本身的问题（评审重点里明确要求指出）

- **Ruling 56 的裁定是对的，但它引用的量级数字是错的**（M3）：`Document/…实施计划01….md:887` 现在写着「实测 2376 个上学年单元格里有 1213 个两张表给出不同得分」，实测旧缺陷只影响 **334** 个（14.1%）。这与 Ruling 61 修掉的「45% vs 26.4%」是**同一类错误第二次发生** —— 上一次是用 `min(gaps)` 概括整组档距分布（Ruling 59 的根因），这一次是把「修复后测试的可分辨性计数」当成「修复前缺陷的影响面」。两次的共同模式是：**一个数字被从一个实验搬到另一个实验的结论里，而没有注明它的测量方向与分母**。建议把这条模式写进账本的教训段。
- **`progress.md:619` 的「只开 `latent_mean`/`latent_sd` 参数位」是事实错误**（M2）：`latent_sd` 从未存在。
- **`progress.md:628` 的「500/17/1000 不翻倍」与工作区实况不符**（M4）：实测 596/17/1826。
- **`progress.md:598` 接受了「四类轨迹分离清晰、方向与标签语义一致」这句结论**（C1）：它紧跟在一张显示「持续下滑 +9.03 / 下降占比 0.00」的表格后面，表格本身就是反证。这是本轮最贵的一次漏检。
- **`progress.md:680` 把「随机流的形状参数」列为三个**，漏了 σ（M2）；也漏了「趋势模型的量级参数（`TREND_PROFILES.prev_offset` / `ITEM_TREND_JITTER_SD` / `INTERVAL_GAIN_MEAN` / `ITEM_TREND_JITTER_SD`）」—— 修 C1/C2/M1 时改的正是这几个常量，改完全量字节都会变，Task 9 派单需要知道这一点。
- **Ruling 34/36/37/38/39/44/52/54/55/57/58/59/60/61 我全部实测复核，未发现新问题**：Ruling 34（问卷只 duplicate）✅、36（列序只从 `base.py`）✅、37（无 `students.csv`、缺失文件 yield 空）✅、38（零填充无 `T`）✅、39（`allow_nan=False`、落盘 0 处 NaN 字面量）✅、44（白名单 11 列 + `*`）✅、52（逐字复制 35/29/6）✅、54(a)（穷举 0 跨档）✅、54(b)/58（28 人、单调性、地板效应）✅、55/60（500→14、120→4）✅、57/59（亚分辨率 0 处、男引体向上恒不抖动）✅、61（132/500=26.4%）✅。
