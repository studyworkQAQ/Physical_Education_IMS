# Task 6 报告：仿真数据生成器（人口学 / 编班 / 体测 / 体成分 / 问卷）

**状态：DONE_WITH_CONCERNS**
分支 `feature/plan-01-data-foundation`，起点 HEAD `3ab32b4`。
测试：**225 passed**（原 201 条全部未改动仍通过 + 新增 24 条），`-W error` 下同样 225 passed、零告警，5.4 s。

---

## 1. 实现内容

按简报的文件清单落地七个模块，职责严格一模块一件：

| 文件 | 行数 | 职责 |
| --- | --- | --- |
| `backend/app/seed/config.py` | 153 | `SeedConfig`、学期日历骨架（`SemesterPlan` / `SEMESTERS` / `timepoint_date` / `semester_end_date` / `BIRTH_REFERENCE_DATE`）、最大余额法配额 `allocate_quota` |
| `backend/app/seed/population.py` | 165 | `make_population`、`birth_date`；姓名 / 院系 / 学号词表；身高体重基准 |
| `backend/app/seed/sections.py` | 121 | `make_teachers`、`administrative_section_count`、`make_sections`（两套编班） |
| `backend/app/seed/fitness.py` | 361 | `latent_profiles`、`make_fitness_tests`、趋势画像 `TREND_PROFILES`、正反查记忆化 `_raw_and_score` |
| `backend/app/seed/body_comp.py` | 122 | `make_body_comp`（InBody 三量，内部自洽） |
| `backend/app/seed/survey.py` | 127 | `make_survey`（5 维度 × 5 点李克特占位量表）、`_likert` |
| `backend/app/seed/generate.py` | 447 | `_organisation`、`build_dataset`、`inject_dirty`、`write_csv`、`seed_database`、`summarize`、CLI `main` |
| `backend/tests/seed/test_generate.py` | 449 | 24 条测试 |

### 1.1 潜变量模型（简报 Step 3 逐字实现）

```
latent_fitness   ~ N(cfg.latent_mean, 1)
latent_endurance = 0.8·fitness + N(0, 0.6)
latent_strength  = 0.7·fitness + N(0, 0.7)
latent_speedflex = 0.6·fitness + N(0, 0.8)
6 项短板判定得分 = clip(70 + 15·latent_所属桶 + N(0, 5), 0, 100)
各项原始值       = raw_from_score(国标表, 项, 得分, 性别, 龄组)
BMI             = 由身高 / 体重分布独立生成后 score_item 正查（**不反查**）
```

残差项 `N(0, 0.6)` 按**标准差**读而不是方差。理由写在 `fitness.py` 的注释里：按方差读会让耐力 / 力量的理论相关系数从 0.57 掉到 0.46，叠上逐项噪声与国标档位离散化后已经贴近「相关系数 > 0.4」那条断言的边界；按标准差读留出的是 0.53 的实测余量。

**没有任何一处对反查结果做舍入**。次数项（引体向上 / 仰卧起坐）的档边界本身就是整数，`raw_from_score` 直接返回可测量读数；任何 `round()` 都可能把 13.5 顶成 14 从而跨档。

**BMI 走正查**：`raw_from_score` 对 BMI 抛 `ValueError`（档位序列非单调）。身高 ~N(172.5/160.5, 6.2/5.6)、BMI ~N(21.8/20.6, 2.9/2.8) 独立生成，`weight = BMI × 身高²`，再 `score_item` 正查得分。

### 1.2 两学年 × 三时点（简报 Step 4）

- 学年：`2024-2025`（上学年）与 `2025-2026`（本学年，`is_current=True`）；各一个学期（`2024-2025-1` / `2025-2026-1`），开学日 2024-09-02 / 2025-09-01（都是星期一），结束日 = 开学日 + `max(weeks, 16)` 周。
- 时点：`week1`/`week8`/`week16` → 开学日 + 0/7/15 周。两学年各三时点 → 每人 6 条体测、6 条体成分、2 份问卷。
- 上学年得分 = 本学年得分 − 趋势项。趋势项 = **一个跨六项共享的标签级偏移** + 每项 `N(0, 1.5)` 抖动（共享项保证一个人六项同向变化，Task 8 判趋势靠的正是这种一致性；抖动保证不会六项严格同步——真实数据里不存在这种学生）。
- 学年内三时点：`week1 = base`、`week8 = base + d₁`、`week16 = base + d₁ + d₂`，`d ~ N(0.8 + cfg.intervention_effect, 1.5 × drift_scale)`。
- `intervention_effect` **只留参数位**（缺省 0.0，加到每个人的间隔增益均值上，不区分实验班 / 对照班）——差异化演进属 Plan 03。

### 1.3 编班（简报 Step 5）

- 行政班：`ceil(500 / 38) = 14` 个，规模 35/36 人（全部落在 30–38），成员用 `rng.permutation` 打散后连续切片，故每班的性别 / 年龄 / 院系构成接近总体。教师按 `index % cfg.teachers` 轮转（`course_section.teacher_id` 非空，14 个班都得有教师；`teachers × sections_per_teacher = 6` 作为班数**下限**，只在它比 `ceil(n/上限)` 大时起作用）。
- 分层班：3 个，按 `latent_fitness` 升序三等分 → 提升班 166 / 强化班 167 / 拓展班 167。排序键带 `student_id` 作稳定次序决胜。
- **全员二次编入**：1000 条选课关系（500 行政 + 500 分层）。
- `stratified` 按 `latent_fitness` 三分位近似分配（简报明写：真实按分层结果编班依赖 Task 9 输出，属计划 04）。

### 1.4 问卷（简报 Step 6）

5 维度（运动乐趣 / 运动能力自信 / 健康认知 / 同伴互动 / 教师评价）× 每维度 2 题 = 10 题，5 点李克特。**维度分由单题算出**（每维度两题取均值），不独立抽两次——否则会出现「维度分 4、底下两题一个 2 一个 5」的自相矛盾记录，而 `raw_answers` 是原样入库的。`total` = 五维度之和，与 `tests/fixtures/lepao_sample/survey.csv` 的口径一致。

李克特取整用 `floor(x + 0.5)` 而不是内建 `round`（银行家舍入会在小整数域上造成可察觉的偶数偏好）。

### 1.5 脏数据注入（Ruling 34 / 44 / 52）

- `missing` 4%、`outlier` 0.5%、`unit_error` 0.3%（前三类按**测量单元格**计，只落 `fitness` 与 `body_comp`）；`duplicate` 1%（按**记录**计，三类源都注入）。
- 注入列白名单从 `app.pipeline.clean.FITNESS_MEASURE_FIELDS` / `BODY_COMP_MEASURE_FIELDS` 推导（它们自己又是从两个原始记录数据类的字段声明序推导的），**没有手抄第二份**，也不可能把日期列或标识列写进来。
- `missing` 一律置 `None`（写盘为空字符串），**不用 0 或负数**——`strength_count = 0` 与负 `sit_and_reach_cm` 是清洗层 designed-to-keep 的真实值。
- `outlier` **只往上抬**（`FieldRange.max × 1.5`），不往下压：往下压对 `strength_count`（下界 0、`zero_allowed`）会落进「负数只能来自未测哨兵」分支产出 `missing_dropped` 而不是 `outlier_corrected`，注入种类于是取决于字段配置。
- `unit_error` 只作用于 `height_cm`（清洗层唯一认得的量纲启发式：`0 < cm < 3` → ×100）。
- `duplicate` **逐字复制整行**（`dict(row)`，在挂痕迹键之前复制），追加到列表末尾。
- 每处注入记一条 `dirty_marks`，字段名与 `CleaningEntry` 对齐，另加 `source` / `row_key` 两个定位列；`kind` 用**注入侧**名字（missing/outlier/unit_error/duplicate），不是清洗侧的 `missing_dropped` 那一套。

### 1.6 CSV 与入库

- `write_csv` 只写 `fitness.csv` / `body_comp.csv` / `survey.csv`；**`students.csv` 有意不产出**（Ruling 37）。文件名与列序一律从 `app.adapters.base` 导入，逐列 `row[column]` 取值（漏列当场 `KeyError`，不会静默产出少列文件）。
- `batch_key` 一律 `base.make_batch_key(...)`；日期一律 `date.isoformat()`（零填充、无时间部分）；JSON 列一律 `json.dumps(..., ensure_ascii=False, allow_nan=False)`；浮点标量另做一次 `math.isfinite` 检查（写侧就拦下来，错误现场才是造出该值的那一行）。
- 行结束符固定 `"\n"`：`csv.writer` 缺省是 `"\r\n"`，那会让「同种子字节级一致」只在同一台机器上成立。
- `seed_database` **只写** semester / teacher / student / course_section / enrollment 五张表，一律走 `repo.upsert` 按自然键幂等更新，父表 flush 后再写子表；**不 commit**（事务边界归调用方，与 `repo.upsert` 口径一致）。体测 / 体成分 / 问卷一律不入库。
- CLI 缺省行为：CSV → `backend/data/seed/`，组织结构 → `backend/pe.db`，控制台打印人数 / 男女比 / 两学年体测条数 / 脏数据注入计数。`--out-csv DIR` 只改 CSV 路径。参数只有简报列出的四个（`--help` 已核对）。

---

## 2. 可复现性证据

### 2.1 同种子字节级一致（跨进程）

两次**独立的** CLI 调用（不同进程、不同输出目录），三个文件的 SHA256 前 16 位完全相同：

```
95657898E573448C  body_comp.csv
E44FC324407E6EF3  fitness.csv
04D0326704ED17CA  survey.csv
```

进程内亦有 `test_same_seed_produces_identical_dataset`（`build_dataset(CFG) == build_dataset(CFG)`，500 人全量字典比较）钉住。

### 2.2 异种子相异

同一目录下用 `seed=1` 重写，三个文件全部 DIFFERENT：

```
seed=1 fitness.csv   e44fc324407e6ef3  f554c940479a1016  DIFFERENT
seed=1 body_comp.csv 95657898e573448c  dd14399a38db0358  DIFFERENT
seed=1 survey.csv    da5126aa36e50c81  949985f2771df84b  DIFFERENT
```

### 2.3 隐藏随机源是怎么排除的

1. **全项目只有一个 `np.random.default_rng()` 调用点**：`generate.py::_organisation` 里那一句 `np.random.default_rng(cfg.seed)`。它返回的 `rng` 被显式穿给 `make_population → latent_profiles → make_sections → make_fitness_tests → make_body_comp → make_survey → inject_dirty`，顺序固定。
2. **源码级守卫**：`test_generators_thread_the_callers_rng_and_never_touch_the_clock` 用 AST 扫 `app/seed/**.py`，凡 `default_rng` 调用（除 `generate.py` 里那一个带参的）、`np.random.seed` / `RandomState` 全局状态写法、`import random`、以及 `date.today` / `datetime.now` / `time.time` 全部记为违规。运行时断言抓不到「恰好这一轮没走到那条分支」，源码级检查可以。
3. **不依赖集合迭代顺序**：`population.py` 里唯一一处 `set` 已改成 `sorted(set(...))`（该字典只被查找、不被遍历，但「不依赖集合顺序」应当写在代码里而不是留给下一个人重新论证）。`allocate_quota` 的余额决胜用**下标**而不是键名比较，故与 dict 哈希序无关。
4. **不依赖浮点求和顺序**：桶均值 `sum(scores[item] for item in items)` 的 `items` 是从 `ITEM_BUCKET` 声明序推导出的**元组**（`_items_by_latent` 的 docstring 明写这一点）；`total = sum(dimensions.values())` 按 `DIMENSIONS` 元组序；`summarize` 里的两处统计一律 `sorted(...)`。
5. **随机数消耗量与配置无关**：`inject_dirty` 对每个测量单元格恰好消耗一次 `rng.random()`、对每条记录恰好消耗一次，与是否真的注入无关。换一组 `cfg.dirty` 比例不会把后面所有数据的取值一起推走。
6. **反查记忆化不引入表间污染**：`_raw_and_score` 的 `memo` 是**每次调用新建的局部字典**，不做模块级缓存（`StandardTable` 装的是 `MappingProxyType`、不可哈希，没法当键的一部分；模块级缓存会在有人拿另一张表调用时静默返回上一张表的结果）。键里的目标分先 `math.floor`：国标档位分全是整数（`load_standard` 用 `int()` 解析），故「不超过 target 的最大官方档」与「不超过 floor(target) 的最大官方档」必然同档，就低语义分毫未变，顺带也满足了 `raw_from_score` 的 `score: int` 标注。键空间从 18000 收缩到约 2000，500 人全量生成 0.19 s。

---

## 3. 观测到的分层相关统计（500 人 / seed=20250828）

正式的 20/45/35 层分布断言属 Task 9（需分层引擎），此处只报观测值。

**得分相关性**（本学年 week1，六项短板判定项的桶均值，n=500）

| 桶对 | 相关系数 |
| --- | --- |
| 耐力 / 力量 | **0.533** |
| 耐力 / 速度柔韧 | 0.428 |
| 力量 / 速度柔韧 | 0.335 |

载荷 0.8 / 0.7 / 0.6 递减，相关系数同序递减——正是单因子结构的指纹，不是独立随机。桶均分 67.6 / 67.4 / 67.5。

**体成分与形态**

| 指标 | 观测值 |
| --- | --- |
| 体脂率异常率（男 >20%、女 >28%） | **0.360**（2919 条有效 / 3033 条） |
| BMI 得分分布 | 100 分 2119 条、80 分 661 条、60 分 34 条 |
| BMI 异常率（得分 < 100） | **0.247** |
| 问卷总分 | 均值 15.9、sd 3.5、范围 5–25（满分 25） |
| corr(问卷总分, latent_fitness) | **0.295** |

**人口学**：男 275 / 女 225（比例精确 0.550）；年龄 18/19/20/21/22 = 132/143/132/80/13；年级 1/2/3/4 = 132/143/132/93（**年龄 → 年级与 `age_group_of` 共用 19/20 那条线**，故 `grade` 与查表用的 `age_group` 永远指向同一个年级组）；12 个院系；500 个学号全唯一。

**四类趋势标签的实际轨迹**（本学年 week1 − 上学年 week1，六项均分差）

| 标签 | n | 均分差 | sd | 下降占比 |
| --- | --- | --- | --- | --- |
| 持续下滑 | 100 | **+9.03** | 2.88 | 0.00 |
| 稳步提升 | 125 | **−7.83** | 2.93 | 1.00 |
| 稳定 | 200 | −0.06 | 1.91 | 0.48 |
| 波动大 | 75 | +0.71 | **6.67** | 0.48 |

四类轨迹分离清晰、方向与标签语义一致；「波动大」的学年内漂移 sd 也是 4.27（对比「稳定」1.60），即它不只学年间跳、学期内也跳。**比例精确命中配置**（200/100/125/75 = 0.40/0.20/0.25/0.15），因为用了最大余额法精确配额而不是逐个抽样。

**编班**：行政班 14 个（规模 35×4 + 36×10，全部在 30–38 内）；分层班 3 个（提升班 166 / 强化班 167 / 拓展班 167）；选课关系 1000 条，全员两套编班。

**脏数据注入**：共 1554 处 —— missing 1291、outlier 173、duplicate 80、unit_error 10。按源拆分：fitness 900/126/10/35，body_comp 391/47/0/33，survey 0/0/0/12（**survey 只有 duplicate**，符合 Ruling 34）。

`dirty_marks` 触及的 `field` 集合恰好是 `{'*'} ∪ 11 个测量列`，**不含任何日期列或标识列**（`test_dirty_marks_never_touch_date_or_identity_columns` 钉住）。

**注入 ↔ 清洗一一对应**（`test_injected_dirt_is_exactly_what_the_cleaning_layer_recognises`，500 人全量走 write_csv → `MockLePaoAdapter` → `clean_fitness` / `clean_body_comp`）：

```
injected total 1554   cleaning entries total 1542
唯一差异：('survey', 'duplicate_removed', '*'): (12, 0)
```

1542 = 1554 − 12 条问卷重复（第一批没有 `clean_survey`，问卷重复由 `uq_interest_survey_student_semester_filled_on` + `repo.upsert` 兜住，Ruling 34）。按 `(source, kind, field)` 三元组比对，**fitness 与 body_comp 的注入痕迹与清洗条目完全相等，一个不多一个不少**。这同时证明了两件事：每一处注入都真的被清洗层认出来且认成期望的那一类；未被注入的干净数据**一条清洗条目都不产生**（生成器画的本底分布没有越出 `indicator_ranges.yaml` 的区间）。清洗后行数 fitness 3000 / body_comp 3000（= 500 × 2 学年 × 3 时点，重复行被去掉后回到原数）；`dropped = 900`、`corrected = 136 = 126 outlier + 10 unit`，duplicate 两个计数都不进（口径与 `clean.py` 的 `_CORRECTED_KINDS` 一致）。

---

## 4. TDD 证据

### RED

```
$ cd backend; python -m pytest tests/seed -q
=================================== ERRORS ====================================
________________ ERROR collecting tests/seed/test_generate.py _________________
ImportError while importing test module '...\backend\tests\seed\test_generate.py'.
tests\seed\test_generate.py:40: in <module>
    from app.seed.body_comp import make_body_comp
E   ModuleNotFoundError: No module named 'app.seed.body_comp'
!!!!!!!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 error in 0.65s
```

**为什么这是预期的失败**：测试先写，`app/seed/` 下当时只有一个空的 `__init__.py`。简报写的期望是 `ModuleNotFoundError: app.seed.config`；实际先炸的是 `app.seed.body_comp`，因为我的 import 块按字母序排列，`body_comp` 在 `config` 之前——同一类失败（模块不存在），只是第一个被解析到的名字不同。

### GREEN

```
$ cd backend; python -m pytest tests/seed -q
........................                                                 [100%]
24 passed in 4.37s

$ cd backend; python -m pytest -q -W error
........................................................................ [ 32%]
........................................................................ [ 64%]
........................................................................ [ 96%]
.........                                                                [100%]
225 passed in 5.53s
```

225 = 原 201 + 新 24。**原有 201 条一条未改**（`git status` 只显示新增文件，无任何既有文件被修改）。

中间还有一次真实的 RED→GREEN：`test_body_fat_abnormal_rate_in_expected_band` 首次运行时炸成
`TypeError: '>' not supported between instances of 'NoneType' and 'int'`——简报那条测试与它自己的 Ruling 34/44 冲突（缺测注入必须落在 `body_fat_pct` 上，于是该列会有 `None`）。处置见 §6 关切 3。

---

## 5. 变更文件

全部为**新增**，无任何既有文件被修改：

```
backend/app/seed/config.py        153 行
backend/app/seed/population.py    165 行
backend/app/seed/sections.py      121 行
backend/app/seed/fitness.py       361 行
backend/app/seed/body_comp.py     122 行
backend/app/seed/survey.py        127 行
backend/app/seed/generate.py      447 行
backend/tests/seed/test_generate.py  449 行
```

`backend/app/seed/__init__.py` 是既有的空文件，未改动。
`.gitignore` 未改动。未新建 `conftest.py`、未新建 `tests/seed/__init__.py`、未引入 linter / Docker / 任何简报未列出的 CLI 参数。

**工作区遗留物（均在 `.gitignore` 内，未入库）**：我实际跑过 CLI，故 `backend/pe.db`（组织结构已入库，跑两次验证过幂等：仍是 500 学生 / 17 教学班 / 1000 选课，数据表全为 0 行）与 `backend/data/seed/{fitness,body_comp,survey}.csv` 现在存在。两者都可由 `--seed 20250828` 复现。

---

## 6. 自审发现与关切

### 关切 1（**需要裁定**）：简报的「12 个行政班」与它自己的另两条断言互斥，我把班数改成反推的 14

简报正文与 `test_two_grouping_modes_coexist` 都写 12 个行政班，同时要求「容纳全部 500 人」且「每班 30–38 人」。三个数不可能同时成立：

```
12 × 38 = 456 < 500          # 装不下全员
500 / 12 = 41.7 > 38         # 每班必然超上限
可行班数区间 = [ceil(500/38), floor(500/30)] = [14, 16]
```

「全员编入」（`test_every_student_enrolled_in_both_grouping_modes`）与「每班 30–38」（`test_administrative_section_size_within_bounds`）都是要被测试钉住、且在教学管理上有实际含义的性质；而 12 只出现在正文与一条断言里，且 `SeedConfig` 的接口清单钉的是 `students=500` 与 `section_size=(30, 38)`（没有钉班数）。所以我**改班数、不改那两条性质**：班数由 `administrative_section_count(students, cfg)` 反推 = `ceil(n / 上限)`，只有当 `n // (teachers × sections_per_teacher) >= 下限` 时才把班数抬到教师下限（缺省下 6 < 14，不起作用）。500 人 → 14 个班，规模 35/36。

测试里的那一行相应改成 `assert len(admin) == 14 and len(strat) == 3`，仍是**等号**、没有放宽，并在测试内注释了上面的算术。若控制方认为该改的是 `section_size` 或 `students`，请裁定，改动很小。

### 关切 2：`make_sections` 加了第四个必需参数 `latents`（偏离简报的接口清单）

简报的接口写 `make_sections(population, cfg, rng)`，但 Step 5 要求阶段二「按 `latent_fitness` 三分位近似分配」。两者不能同时成立。我加了第四个**必需**位置参数 `latents`，并且**故意不给它「按学号顺序三等分」的缺省值**：那种退化分配不报错，只会静默产出与体能毫无关系的分层班，而这三个班正是阶段二演示的全部内容。

同类偏离还有一处，方向相反：`inject_dirty(records, cfg, rng)` 的三参数签名被**逐字保留**。它需要知道记录属于哪一类源才能选对测量列白名单，做法是从记录的形状推断（有 `batch_key` → fitness、有 `measured_on` → body_comp、有 `filled_on` → survey），而不是多收一个 `source` 参数。

### 关切 3：简报的 `test_body_fat_abnormal_rate_in_expected_band` 与 Ruling 34/44 冲突，我改了两行并**加**了一条守卫

Ruling 34 要求 `missing` 注入落到 `body_comp`，Ruling 44 的白名单里明写 `body_fat_pct`；4% 的缺测率于是让约 114 条记录的 `body_fat_pct` 是 `None`，而简报那条测试直接 `r["body_fat_pct"] > 阈值`，在 `None` 上炸 `TypeError`。

处置：过滤掉被置空的单元格（该断言量的是**生成器的分布**，不是脏数据的分布），并**新增**一条分母守卫 `len(measured) > 0.9 * len(ds["body_comp"])`，堵住「把大多数记录过滤掉从而让 0.20–0.50 这个区间失去意义」这条退路。原区间 `0.20 <= rate <= 0.50` 一字未改。实测 rate = 0.360、存活 2919/3033 = 96.2%。

### 关切 4：简报 Step 3 的「二分法调 μ」**没有实现**，只开了参数位

「用二分法调 μ 使生成人群的红/黄/绿比例逼近 `target_layer_dist`」需要 Task 9 的分层引擎才能算出红黄绿，而简报自己也明写「**该分布断言在 Task 9 落地**，本 Task 只保证潜变量与得分生成正确」。我因此没有去猜一套临时的分层规则来实现二分法（那会与 Task 9 的实现冲突，而且猜出来的规则不会报错、只会静默给出一个错的分层）。

落地方式：`SeedConfig.latent_mean: float = 0.0`（缺省标准正态），Task 9 只需对它做二分即可，不必改函数签名。**需要裁定的副作用**：μ=0 时六项桶均分实测约 67.5 而不是 70——因为 `raw_from_score` 的就低取档在低分区（档距 10 分）把连续目标分系统性地往下压，而在高分区（档距 2 分）几乎不压。这个偏斜是国标档位表本身的性质，不是缺陷；但 Task 9 调 μ 时会看到「μ 加 1 分、桶均分加不到 1 分」，请预先知悉。

### 关切 5：男生引体向上**永远生成不出 0–4 次**

国标表里男性「大一、大二」引体向上的最低档是 **5 次 = 10 分**（`segment_thresholds` 实测 raw 区间 5.0–19.0）。`raw_from_score(..., 目标分 ≤ 10, ...)` 只能返回 5.0，而简报 Step 3 明确规定「各项原始值 = `raw_from_score(得分, 性别, 龄组)`」，所以数据集中男生的 `strength_count` 最小值就是 5.0，**不存在「一个引体向上也做不起」的学生**。

真实高校数据里 0–4 次的男生占比相当高（这正是引体向上成为普遍短板的原因）。后果：本原型的力量桶短板尾部比真实情况薄，红色层里「因力量短板而入层」的人会偏少。`score_item` 本身对低于表内最低档的值是**低侧夹取到最低档分**的（`score_item(T, PULL_UP_OR_SIT_UP, 0.0, MALE, G) == 10`），所以生成 0–4 次在评分侧完全安全；缺的只是简报没给这条路。**请裁定是否要加一个「表下溢出」机制**（例如对目标分 ≤ 最低档的学生按一定概率把原始值再往下压到 `[0, 表内最低 raw)`）。我没有自行加：它会让「原始值 = 反查结果」这条不变式出现例外，而 `test_generated_raw_values_roundtrip_through_the_official_table` 正是要钉这条不变式的。

### 关切 6：`score_*` 列在脏数据注入后与原始值不再自洽（有意为之）

`ds["fitness"]` 每行带 7 个 `score_<项名>` 与 3 个 `score_<桶名>_mean`，它们是**生成期的诊断量**（用来验证反查确实落回目标档位、并让「耐力/力量正相关」这条断言有得可算）。缺测注入会把原始值置空而**不会**回算这些列，所以被注入过的行上两者不再自洽。

这是有意的：这些列**既不写盘也不入库**（`write_csv` 只挑 11 个契约列；`seed_database` 只写五张组织结构表），管道一律从清洗后的原始值重新正查得分——生成器算的分数不是第二份真相。`fitness.py::make_fitness_tests` 的 docstring 明写了这一点。

### 关切 7：两学年的年级 / 年龄是「以当前学期开学日为参考日」的快照，上学年并未回退一个年级

`BIRTH_REFERENCE_DATE = 当前学期开学日 = 2025-09-01`，`grade` 与 `age` 都据此固定。严格说，同一个学生在 2024-2025 学年应当低一个年级、小一岁，而 `student.grade` 只有一个列、`birth` 也只有一个值，无法同时表达两个学年。

影响很小且方向明确：上学年的体测记录会按**本学年**的年龄组查表（19 岁的学生在上学年那三条记录里仍按「大一、大二」查表，而他当时本该是 18 岁的大一——同一个年级组，查的是同一张表）。**只有跨 19/20 那条线的学生会真的查错组**：本学年 20 岁（大三）的学生，上学年 19 岁本该按「大一、大二」查表，而我们按「大三、大四」查。按当前年龄分布（20 岁及以上占 45%），这部分学生的上学年记录用的是偏严一档的评分表。已在 `population.py` 与 `config.py` 的 docstring 里写明参考日及其理由。请裁定是否可接受；若要修，做法是给上学年的记录另算一个 `age_group`（不入库、只影响生成时查哪张表），改动约 10 行。

### 关切 8：`generate.py` 447 行

按简报的文件清单，`generate.py` 同时拥有 `build_dataset` / `inject_dirty` / `write_csv` / `seed_database` / CLI，447 行里超过一半是中文 docstring 与注释。我**没有自行拆分**（例如把 `inject_dirty` 挪到独立模块），因为简报的文件清单是七个文件、拆出第八个属于结构性改动。若控制方认为该拆，最自然的切法是把 `inject_dirty` + `_locate` + `_damage` + `_mark`（约 130 行）移到 `app/seed/dirty.py`。

### 关切 9：`muscle_mass_kg` 的下界夹取会在 <1% 的记录上真的生效

肌肉量由 `SMI × 身高² × 1.5` 算出（三个量内部自洽，不独立抽三次）。最矮的学生（152 cm）配上最低的 SMI（5.0）会得到 17.3 kg，低于 `indicator_ranges.yaml` 的合理下界 20，故被夹到 22.0。这类记录占比不足 1%，夹后仍在生理上说得过去，换来的是「生成的干净数据一条都不会被清洗层当异常值夹取」这条整体保证（§3 的清洗对账已实测证实）。折算系数 1.5 是量级近似（真实比值随性别与训练水平在 1.5–1.8 之间），选它的判据是「算出来的分布落在 InBody 对中国大学生的常见读数区间」，已在 `body_comp.py` 注释里写明。

### 关切 10：简报的 `test_write_csv_roundtrips_through_adapter` 用 40 人，此时行政班规模必然低于下限

40 人无法分成 30–38 人的班（1 个班 40 人超上限，2 个班各 20 人低于下限）。`administrative_section_count(40, cfg)` 返回 2、每班 20 人。这是规模本身造成的不可行，不是缺陷；该测试只断言写盘往返，不断言班规模，故照简报原文保留 40 人。**顺带说明**：`SMALL = 120` 是我给「与规模无关」的断言选的配置，120 恰好是能同时满足每班 30–38 人的最小可编班规模（4 个班 × 30 人）。

### 关切 11：BMI 与体脂率**不耦合**

简报 Step 3 明写「BMI 得分 = 由身高体重分布独立生成后正查评分表」，故 BMI 完全独立于 `latent_fitness`；而体脂率按 `latent_fitness` 牵引（男 −3.0、女 −3.5 的斜率）。真实数据里两者应当正相关（体脂高的人 BMI 通常也高），本数据集里它们只有很弱的相关。这是照简报实现的结果，不是疏漏；若控制方要求耦合，改 `population.py` 的 BMI 基准一行即可（但那样就需要 `make_population` 也接收潜变量，而潜变量目前是在人口学之后生成的——顺序要反过来）。

### 关切 12：新增测试 24 条而不是简报期望的 13 条

多出的 11 条逐条可追溯到简报正文或裁定的**明确要求**，没有一条是我自行加戏：

| 测试 | 依据 |
| --- | --- |
| `test_dirty_marks_never_touch_date_or_identity_columns` | 任务书明写「A test must assert `dirty_marks` contains no date or identity column」；Ruling 44 |
| `test_duplicate_injection_copies_the_whole_row_verbatim` | Ruling 52 |
| `test_survey_records_only_ever_receive_duplicate_injection` | Ruling 34 |
| `test_trend_labels_are_injected_at_configured_ratios` | 简报 Step 4「四类比例注入」 |
| `test_generated_raw_values_roundtrip_through_the_official_table` | Ruling 18/22 的精确往返，在真实生成数据上验 |
| `test_write_csv_emits_exactly_the_three_contract_files` | Ruling 36/37/38（含 `students.csv` 有意缺席、日期格式、`make_batch_key` 往返） |
| `test_survey_total_is_weakly_correlated_with_latent_fitness` | 简报 Step 6「相关系数约 0.3」 |
| `test_injected_dirt_is_exactly_what_the_cleaning_layer_recognises` | 简报 Step 6「每处注入记一条 `dirty_marks` **供 Task 5 清洗测试交叉验证**」——Task 5 已完成，交叉验证只能落在这里 |
| `test_seed_database_writes_only_organisation_tables_and_is_idempotent` | 简报 Step 6「只写组织结构……不得直接入库」 |
| `test_generators_thread_the_callers_rng_and_never_touch_the_clock` | 任务书的自审清单第一条（隐藏 RNG） |
| `test_inject_dirty_leaves_clean_records_untouched_when_all_rates_are_zero` | 「注入是唯一脏数据来源」的反向证据 |

### 自审清单逐条核对

- **可复现**：§2 全部通过；无隐藏 RNG（AST 守卫）、无集合序依赖（唯一一处 `set` 已 `sorted`）、无浮点求和序依赖（桶均值按元组序）。
- **真实性**：耐力/力量相关 0.533（> 0.4）；体脂异常率 0.360、BMI 异常率 0.247，都在 20–40% 区间内。
- **两学年**：`2024-2025` 1515 条 + `2025-2026` 1520 条（多出的是 duplicate 注入）；四类趋势标签精确按 20/15/25/40 注入，实际轨迹见 §3。
- **三时点**：本学年 `{week1, week8, week16}` 齐全（上学年同样三时点）。
- **两套编班**：14 个行政班（35/36 人，全在 30–38 内）+ 3 个分层班（提升班 / 强化班 / 拓展班），全员两套都在。
- **问卷**：5 维度、每维度 1–5、`total` 5–25、与 `latent_fitness` 相关 0.295。
- **脏数据**：四类齐全；`dirty_marks` 的 `field` 集合恰为 `{'*'} ∪ 11 个测量列`，无日期列、无标识列。
- **CSV 往返**：`write_csv` 的输出经 `MockLePaoAdapter` 三个 `fetch_*` 全部读回成功，并进一步经 `clean_fitness` / `clean_body_comp` 与注入痕迹一一对账（§3）。
- **`seed_database`**：只写五张组织结构表，九张数据表全为 0 行；跑两次幂等（500/17/1000 不翻倍）。
- **原有测试**：201 条一条未改，`git status` 只显示新增文件；`-W error` 下 225 passed、输出洁净。
- **无多余产物**：无 `conftest.py`、无 `tests/seed/__init__.py`、无 linter / Docker、CLI 只有简报列出的四个参数。

---

## Fix Round 1

派单简报：`task-6-fix1-brief.md`（Ruling 54 含控制者的两条修正 Ruling 57/58、Ruling 55 只核实、Ruling 56）。
基线 `826f72a`（工作树干净）→ 本轮**一个** commit `34691f9`（4 文件、+721 / −14）。
测试 **225 → 236 passed**（新增 11 条，既有测试只改了 1 条的龄组取法），`-W error` 同样 **236 passed**、输出洁净、**12.5 s**。

变更文件：

```
backend/app/seed/config.py          +15    SeedConfig 增 jitter_within_band / sub_floor_rate
backend/app/seed/fitness.py        +220    MEASURE_DECIMALS、jitter_raw、sub_floor_marks、记录循环两处后处理、Ruling 56 的龄组
backend/tests/seed/test_fitness.py +491    新增文件，11 条测试
backend/tests/seed/test_generate.py   +9/-2 roundtrip 那条改为按记录所属学年取龄组
```

未改：`app/domain/indicators.py`（一个字未动，含未给 `_lower_is_better` 加别名）、`sections.py`、`write_csv` 的三个文件契约、`allow_nan=False`、`make_batch_key`、日期零填充；未加 `students.csv`。

---

### F1. Ruling 56 —— 上学年记录按上学年年龄组查表

#### F1.1 改动前的失败证据（简报 §3 要求的「唯一能证明该缺陷真实存在的证据」）

先改测试（`test_generated_raw_values_roundtrip_through_the_official_table` 的龄组取法 + 新增 `test_previous_year_records_use_the_previous_year_age_group`），**在实现未动**的情况下跑：

```
$ cd backend; python -m pytest tests/seed -q -k "previous_year_age_group or roundtrip"
        checked = 0
        current_year = current_semester().academic_year
        for r in ds["fitness"]:
            person = pop[r["student_id"]]
            sex = Sex(person["sex"])
            age_group = age_group_of(
                person["age"] if r["academic_year"] == current_year else person["age"] - 1
            )
            for item in WEAKNESS_ITEMS:
                column = column_of[item.value]
                if (r["student_no"], column) in dirty:
                    continue
                raw = r[column]
>               assert score_item(table, item, raw, sex, age_group) == r[f"score_{item.value}"]
E               AssertionError: assert 80 == 76
E                +  where 80 = score_item(StandardTable(segments=mappingproxy({...})),
E                          <ScoredItem.PULL_UP_OR_SIT_UP: 'pull_up_or_sit_up'>, 15.0,
E                          <Sex.MALE: 'male'>, '大一、大二')
tests\seed\test_generate.py:311: AssertionError
=========================== short test summary info ===========================
FAILED tests/seed/test_fitness.py::test_previous_year_records_use_the_previous_year_age_group -
  AssertionError: 学号 2023090001 上学年 pull_up_or_sit_up 原始值 15.0：记录里是 76 分，
  按上学年龄组 大一、大二 查表应是 80 分
assert 76 == 80
FAILED tests/seed/test_generate.py::test_generated_raw_values_roundtrip_through_the_official_table -
  AssertionError: assert 80 == 76
2 failed, 1 passed, 22 deselected in 1.54s
```

一条具体的跨线学生：**学号 2023090001（age = 20，男生）**，上学年引体向上原始值 **15.0 次**，生成器记下的是 **76 分**（用本学年的「大三、大四」表算的：该表 15 次 → 76 分），而这条记录**所属学年**该生 19 岁、属「大一、大二」组，那张表 15 次 → **80 分**。实际 76 vs 期望 80，差 4 分。两条测试都在这同一个事实上炸开；改动后两条全绿。

#### F1.2 缺陷的量级（实测，500 人 / seed=20250828）

| 量 | 实测值 |
| --- | --- |
| 跨线学生（`age == 20`） | **132 / 500 = 26.4%**（不是简报写的 45%，见关切 B） |
| 受影响的上学年记录 | 396 条（132 人 × 3 时点） |
| 两表给出**不同**得分的 (记录, 项) 单元格 | **1213 / 2376 = 51.1%**；132 名跨线学生**人人**至少有一格能被分辨 |
| 旧代码下管道按上学年龄组重算的偏差 | 均值 **+0.827 分/项**（1827 个未注入单元格） |
| 逐项偏差 | 引体向上 **+2.72**（46.3% 的单元格非零，最大 +10）、肺活量 +1.40（17.0%）、50 米跑 +0.82（16.5%）、坐位体前屈 / 立定跳远 / 耐力跑 **0.00**（0%） |

偏差的方向：上学年得分被**高估**，故趋势（本学年 − 上学年）被**系统性低估** 0.83 分/项——而趋势是分层规则 Y4 的唯一输入。

坐位体前屈 / 立定跳远 / 耐力跑三项偏差恰为 0 的原因（不是巧合，是表的结构）：这三项两个龄组的阈值差（0.5 cm / 2 cm / 2 s）**小于**其档距（1.0 cm / 3–4 cm / 5–20 s），故把高龄组的端点拿到低龄组表上重查仍落在同一档内。引体向上的组间差是 1 次、档距也恰是 1 次，于是**精确落到下一个阈值**上，偏差最大——这也解释了为什么 F1.1 的失败首先出现在这一项。

#### F1.3 改动

`app/seed/fitness.py` 记录循环里的一行（加 8 行注释说明它为什么承重）：

```python
age_group = age_group_of(
    person["age"] if plan.is_current else person["age"] - 1
)
```

该 `age_group` 贯穿本条记录的**全部**查表：`score_item(..., ScoredItem.BMI, ...)` 正查、`_raw_and_score(...)` 的六项反查与回读、以及 Ruling 54(b) 的 `floor_raw = int(min(segment_thresholds(table, item, sex, age_group)))`。

**memo 不串味已复核（简报 §3 要求「别假设」）**，两路证据：

1. 键的字面构造：`key = (item.value, sex.value, age_group, math.floor(target))`——`age_group` 在键里。
2. 实测（同一 memo 遍历 6 项 × 2 性别 × 10..100 共 1092 个 `(item, score, sex)` 三元组）：两个龄组下 **1092 组结果全部不同、0 组相同**，memo 条目数 2184 = 1092 × 2；再用一个新建 memo 复算同一批调用，**不一致条数 0**（无状态污染）。也就是说：若 memo 真被污染，这 1092 组会全错，而 F1.1 那条 roundtrip 测试（用记录**所属学年**的龄组复核）会立刻炸开——它不是只靠读代码保证的。

`age_group_of(17)` 实测返回「大一、大二」，故 `age - 1 == 17` 不会 KeyError（与简报 §3 末尾的预期一致）。

---

### F2. Ruling 54(a) —— 档内抖动

**配置**：`SeedConfig.jitter_within_band: bool = True`（默认开）。
**分辨率**：模块级 `MEASURE_DECIMALS`（肺活量/立定跳远/次数 = 0 位，50 米/坐位体前屈/耐力跑 = 1 位），**未**放进 `SeedConfig`——它是仪器与上报口径的知识，不是旋钮。
**算法**：`jitter_raw(table, item, raw, sex, age_group, rng)` 按简报 §4.2 逐字实现——整数单位（`scale = 10 ** d`）、`lo/hi` 由相邻阈值定、`lo >= hi` 时**直接返回端点且不消耗随机数**、否则 `lo + rng.integers(0, hi - lo + 1)` 再 `/ scale`。
**方向判定不碰私有 API**：新增 `_band_is_lower_better`，只用 `segment_thresholds`（升序）+ `score_item` 回读首末两点，未 import `_lower_is_better`。
**抖动不进 memo**：它在记录循环里、拿到 `(raw, realised)` 之后施加，每条记录抽一次；`_raw_and_score` 仍返回 `(端点, realised)` 并继续记忆化。
**随机数消耗顺序**：记录循环内按 `WEAKNESS_ITEMS` 声明序逐项处理，只在有空间时抽数；已写进 `make_fitness_tests` 的 docstring，并注明「改 `MEASURE_DECIMALS` 会整体平移随机流、改变同一种子的输出，这是配置变更的预期后果」。
**次数类无单独取整分支**：`d = 0`、`scale = 1`，整数单位就是次数本身——这一点按简报要求写进了 `jitter_raw` 的 docstring（「Ruling 54 原文那句『次数类向下取整再回验』在此是多余的——不是漏了，是不需要」）。

**实测效果**（500 人默认配置；「非本组阈值」= 该记录的原始值不等于**它自己那一组** `(item, sex, age_group)` 的任何阈值，已排除被注入过的单元格）：

| 列 | 不同取值个数 | 官方阈值个数（4 组并集） | 非本组阈值占比 |
| --- | --- | --- | --- |
| `vital_capacity_ml` | **1736**（排除注入单元格后 1523） | 75 | **96.1%** |
| `distance_run_s` | 1047（970） | 66 | 92.9% |
| `sit_and_reach_cm` | 262（260） | 75 | 87.9% |
| `standing_jump_cm` | 146（143） | 77 | 73.7% |
| `sprint_50m_s` | 44（43） | 48 | **42.2%**（见关切 A） |
| `strength_count` | 58（57） | 51 | 29.7%（含表下溢出的 5 个值） |

「所有肺活量都是 120 的整数倍」这个症状已消除：肺活量现有 **1736** 个不同取值，而官方阈值只有 **75** 个（端到端回归 `test_full_dataset_raw_values_are_not_all_band_endpoints` 钉住「不同取值个数 > 官方档位数」，并额外要求非阈值取值 > 100 个）。

---

### F3. Ruling 54(b) —— 表下溢出（按 Ruling 58 的排序选取，不按记录掷骰子）

**配置**：`SeedConfig.sub_floor_rate: dict[str, float] = {"male:pull_up_or_sit_up": 0.10}`，键格式 `"<sex.value>:<item.value>"`。
**选取**：`sub_floor_marks(population, latents, cfg)` → `{(sex.value, item): frozenset(student_id)}`。按 `latents[sid][LATENT_BY_BUCKET[ITEM_BUCKET[item]]]`（即 `strength`）**升序**、平手按 `student_id` 决胜，取前 `int(round(n * rate))` 名，构成**该生的持久标记集合**（两学年六个时点都算）。该函数**不消耗随机数**（纯排序 + 计数）。
**取值**：标记集合内的学生，该项每条记录 `float(int(rng.integers(0, floor_raw)))`，`floor_raw = int(min(segment_thresholds(table, item, sex, 该记录的 age_group)))`——随 Ruling 56 的龄组走（男 大一二 = 5、大三四 = 6），**逐条重抽**以体现测量波动。
**得分**：一律 `score_item(table, item, 溢出值, sex, age_group)`，由 Ruling 17 的低侧夹取自动等于底档分；**未写死 10**（实测两个龄组的底档分都是 10，但那是查出来的，不是硬编码的）。
**未知键响亮报错**：`ValueError`，消息含全部合法键清单。

**实测**（500 人 / seed=20250828）：

| 量 | 实测值 |
| --- | --- |
| 男生数 | 275 |
| 被标记男生数 | **28** == `int(round(275 * 0.10))` |
| 被标记者 `latent_strength` 最大值 | **−1.1447** |
| 未标记者 `latent_strength` 最小值 | **−1.1196**（严格大于上者 → 单调性成立，无一处逆序） |
| 被标记者的记录数 | 168 条（28 人 × 6 时点），全部低于本组表内最低档 |
| `strength_count` 分布（记录级） | **0 → 35 条、1 → 28 条、2 → 28 条、3 → 32 条、4 → 32 条、5 → 13 条** |
| 按龄组拆分 | 大一、大二（底档 5）：0–4 共 126 条；大三、大四（底档 6）：0–5 共 42 条，取值 **5 只出现在这一组** |
| 每人的最小次数分布 | 0 → 20 人、1 → 5 人、2 → 2 人、3 → 1 人（逐条重抽确实产生了波动） |
| 被标记者的 `score_pull_up_or_sit_up` | 取值集合 = **{10}**（两个龄组的底档分都是 10） |
| 未标记男生的 `strength_count` 最小值 | 7.0（≥ 各自龄组的底档 5/6） |
| 该项学年间趋势（28 人） | 全部 = **0.0**（地板效应，见前向约束） |
| 男生力量桶均分（本学年 week1） | 均值 65.65、sd 18.40、P25 57.00、最小 15.00；引体向上得 10 分者 28 / 275 |

---

### F4. Ruling 55 —— 核实结论

**已核实，无需改动**：`sections.py:administrative_section_count` 在缺省配置（`section_size=(30, 38)`、`teachers=3`、`sections_per_teacher=2`）下，500 人 → `max(ceil(500/38), 6) = 14` 个班，每班 35/36 人，全部落在 `[30, 38]`；`tests/seed/test_generate.py:138` 的 `len(admin) == 14` 是**等号**断言、未放宽；计划 Step 5 与 spec §10.3 的勘误与之一致。

**但计划 Step 5 的退化子句与实现不一致**（简报 §2 要求「若发现不一致，上报，不要自行改」，故未改）：实测 n=120 时字面公式 `max(ceil(n/high), teachers×spt)` 给 **6**、实现给 **4**；n=40 时给 **6** vs **2**。详见关切 C。

---

### F5. 测试与取证

#### F5.1 测试数、`-W error`、耗时

```
$ cd backend; python -m pytest -q
236 passed in 12.23s

$ cd backend; python -m pytest -q -W error
236 passed in 12.47s        # 输出洁净，无 warning、无 DeprecationWarning
```

**225 → 236**（+11）。基线在动手前已复跑确认为 `225 passed in 6.75s`。`tests/seed` 单独跑：24 → **35 passed**。

新增 11 条（全部在 `backend/tests/seed/test_fitness.py`，新文件）：

| # | 测试 | 依据 |
| --- | --- | --- |
| 1 | `test_previous_year_records_use_the_previous_year_age_group` | Ruling 56（简报 §3 点名的那条独立测试） |
| 2 | `test_jitter_never_crosses_a_score_band` | 简报 §4.4 #1：6 项 × 2 性别 × 2 龄组 × 全部官方档，每档 50 次（实跑 22800 次抖动，全部档位不变） |
| 3 | `test_jittered_values_respect_measure_resolution` | 简报 §4.4 #2：整数单位判定，不用浮点取模 |
| 4 | `test_jitter_is_effective_where_the_band_is_wider_than_resolution` | 简报 §4.4 #3：逐档判定「有格点空间必须抖开、没有必须原样返回」 |
| 5 | `test_measure_decimals_match_the_official_reporting_resolution` | **超出简报清单**，理由见 F6.3 |
| 6 | `test_full_dataset_raw_values_are_not_all_band_endpoints` | 简报 §4.4 #4 |
| 7 | `test_jitter_can_be_disabled_by_config` | 简报 §4.4 #5（见关切 E） |
| 8 | `test_sub_floor_targets_the_weakest_students_by_latent` | 简报 §4.4 #6：人数等号 + 单调性（最强形式：被标记者的最大潜变量 ≤ 未标记者的最小潜变量） |
| 9 | `test_sub_floor_values_are_below_the_table_floor` | 简报 §4.4 #7，另加「标记是持久的」与「逐条重抽确有波动」两条 |
| 10 | `test_sub_floor_rate_rejects_unknown_keys` | 简报 §4.4 #8（三个坏键：`male:no_such_item` / `female:bmi` / `bmi:male`） |
| 11 | `test_sub_floor_can_be_disabled` | 简报 §4.4 #9：六项 × 两性别全查，无一条低于表内最低档 |

#### F5.2 可复现性取证（重做，因为输出字节必然全变）

两次**独立 CLI 进程**（`python -m app.seed.generate --out-csv <dir>`，不同进程、不同输出目录），三个 CSV 的 SHA256 前 16 位**逐一相同**；第三次换 `--seed 1`，三个文件**全部不同**：

| 文件 | 进程 A | 进程 B | A vs B | seed=1（进程 C） | A vs C | 字节数 |
| --- | --- | --- | --- | --- | --- | --- |
| `fitness.csv` | `35A0E49CB118DB55` | `35A0E49CB118DB55` | **IDENTICAL** | `6EEEC113B6040FAA` | **DIFFERENT** | 244723 |
| `body_comp.csv` | `0ECDDABA7531817A` | `0ECDDABA7531817A` | **IDENTICAL** | `BB36AD613F66A2CF` | **DIFFERENT** | 107559 |
| `survey.csv` | `DAF36973A0DA49D6` | `DAF36973A0DA49D6` | **IDENTICAL** | `B00E217D3743DAD0` | **DIFFERENT** | 275640 |

（上一轮的 `E44FC324407E6EF3` / `95657898E573448C` / `04D0326704ED17CA` 已全部作废。）
输出目录里**恰好三个文件**，无 `students.csv`（Ruling 37 复验）。进程内另有 `test_same_seed_produces_identical_dataset`（500 人全量字典 `==`）钉住。AST 源码守卫（禁第二个 `default_rng` / `np.random.seed` / `import random` / `date.today`）本轮未放宽、仍全绿——新增的 `jitter_raw` / `sub_floor_marks` 一律用调用方传入的 `rng`。

CLI 摘要（500 人 / seed=20250828）：人数 500（男 275 / 女 225，0.550）；体测记录 **3035** 条（2024-2025 1525、2025-2026 1510）；体成分 3029 条、问卷 1006 份；教学班 17 个、选课关系 1000 条；脏数据注入 **1572** 处（missing 1318、outlier 173、duplicate 70、unit_error 11）。

#### F5.3 相关系数与其它观测量（本学年 week1，桶均值，n=500）

| 桶对 | 上一轮 | **本轮** | 断言 |
| --- | --- | --- | --- |
| 耐力 / 力量 | 0.533 | **0.5211** | `> 0.4` ✅ **阈值一字未改** |
| 耐力 / 速度柔韧 | 0.428 | **0.4330** | — |
| 力量 / 速度柔韧 | 0.335 | **0.3418** | — |

桶均分：耐力 67.62（上轮 67.6）、力量 **66.51**（上轮 67.4）、速度柔韧 67.62（上轮 67.5）。力量桶下降 0.9 分正是表下溢出把 28 名男生的引体向上钉在底档的结果，是 Ruling 54(b) 要制造的低尾，不是相关性退化。

**肺活量不同取值个数：1736**（官方阈值 75 个）。
**被标记男生数：28**；其 `strength_count` 分布 **0/1/2/3/4 = 35/28/28/32/32 条**（另有 13 条取值 5，全部来自表内最低档为 6 的「大三、大四」组）。

#### F5.4 TDD 顺序（Ruling 54 一侧）

1. 先写 9 条测试 → 收集期即失败：`ImportError: cannot import name 'MEASURE_DECIMALS' from 'app.seed.fitness'`（`1 error in 0.34s`）。
2. 实现 `MEASURE_DECIMALS` / `jitter_raw` / `sub_floor_marks` / 记录循环改动 → `1 failed, 33 passed in 10.91s`，唯一失败的是：

```
>                   assert drawn == {endpoint}, (
E                   AssertionError: sprint_50m/male/大一、大二 档 10：档距等于测量分辨率，
E                   按 Ruling 57 不得抖动，实际得到 [10.0, 10.1]
E                   assert {10.0, 10.1} == {10.1}
```

这是一次**真实的 RED**，而且它证伪的是简报 §4.1 的前提而不是我的实现：实测 50 米跑的档距**并非处处 0.1 s**（男生大一/大二 20 个阈值里只有最高 4 档是 0.1 s，其余 15 档是 **0.2 s**；女生另有两档 0.3 s），于是底档 `(9.9, 10.1]` 里的 10.0 s 是**合法的真实测量读数**，按 §4.2 的算法必然会被抖出来。我保留了 §4.2 的算法（不为某一项开特例），把那条测试改成**逐档数据驱动**（空间由 `_room_in_units` 从评分表独立推导，不复用实现的算式），并另加 #5 把 `MEASURE_DECIMALS` 字面钉死。详见关切 A。
3. 全绿：`35 passed`（tests/seed）→ `236 passed`（全量）→ `236 passed -W error`。

---

### F6. 被调整的既有测试（逐条，含理由）

#### F6.1 `test_generated_raw_values_roundtrip_through_the_official_table`（`tests/seed/test_generate.py`）

**改了什么**：复核用的龄组由 `age_group_of(person["age"])` 改为按**记录所属学年**取（本学年 `age`、上学年 `age - 1`），并在 docstring 里写明理由。共 +9 / −2 行。
**为什么**：Ruling 56。测试原先与生成器犯同一个错（两边都用本学年龄组），所以互相印证、双双通过；只有把**测试一侧**改对，缺陷才暴露出来（F1.1 的 RED 就是这么来的）。
**是否放宽**：**没有**。断言仍是全称等号 `score_item(...) == r[f"score_{item.value}"]`，`checked > 1000` 的下限未动，脏单元格过滤逻辑未动。改的是「用哪张表复核」，不是「复核多严」。

#### F6.2 其余既有测试**一条未改**

225 → 236 的 11 条差额全部是新增；`test_generate.py` 除 F6.1 外无改动（`git diff --stat` 可验：该文件 +9/−2）。特别点名简报 §4.4 提到的三条：

- `test_indicator_correlation_is_realistic`：**0.4 阈值一字未改**，实测 0.5211（F5.3）。简报允许调阈值，但没有必要，故未动。
- `test_same_seed_produces_identical_dataset` / `test_different_seed_produces_different_dataset`：未动。输出字节确实全变（F5.2），但这两条断言的是「两次相同 / 异种子相异」，与具体字节无关；CSV 哈希取证在测试之外重做。
- `test_injected_dirt_is_exactly_what_the_cleaning_layer_recognises`：未动，仍全绿。注入总数从 1554 变成 **1572**（随机流被抖动/溢出平移的必然结果），而这条测试比的是「注入痕迹 == 清洗条目」两侧计数相等，故与绝对数无关；差额仍恰为问卷的 duplicate 条数（第一批无 `clean_survey`，Ruling 34）。**干净数据仍产生 0 条清洗条目**——这一点尤其值得说明：表下溢出生成的 0–5 次落在 `indicator_ranges.yaml` 的 `strength_count`（`min: 0`、`zero_allowed: true`、`non_positive_is_missing: false`）之内，抖动值一律在同档带内，故两者都不会被清洗层判为越界。若有一处越界，这条测试会以「清洗条目多于注入痕迹」的形式当场炸开。

#### F6.3 本轮**新增**测试自身的一次修正（不是既有测试）

`test_jitter_is_effective_where_the_band_is_wider_than_resolution` 首版按简报 §4.4 #3 的字面写死了「`sprint_50m` 与男生 `strength_count` 抖动恒等于端点」，实测失败（F5.4 第 2 步）。改成逐档数据驱动后，它**同时**覆盖了两类断言且更强：空间 ≤ 1 格点的档必须恒等于端点（男生引体向上 30 个档全部如此，断言 `wide == 0` 且 `narrow == 15 × 2`），空间 ≥ 2 格点的档必须至少抖出 2 个不同取值，且每个抖动值回查仍是同一档。

**为什么另加 #5 `test_measure_decimals_match_the_official_reporting_resolution`**：#3 的分辨率断言是从 `MEASURE_DECIMALS[item]` 读 `scale` 的，所以有人把 50 米改成 2 位小数（生成 6.73 s）时它会**跟着一起通过**——简报 §4.4 #3 括号里那个目的（「防止后来人顺手把 50 米改成 0.01 s」）单靠 #3 达不到。#5 把常量逐字钉死（`assert MEASURE_DECIMALS == {...}` 且 `set(MEASURE_DECIMALS) == set(WEAKNESS_ITEMS)`），是那个漏洞的唯一堵点。这是本轮唯一超出简报清单的测试。

---

### F7. 关切

#### 关切 A（**需要裁定**）：简报 §4.1 / Ruling 57 关于 50 米跑的事实前提是错的——档距并非「全部 0.1 s」

Ruling 57 写「50 米跑的档距恰为 0.1 s（全部 4 组）……于是表内每一个 0.1 的整数倍都是阈值」，并据此裁定「50 米跑与男生引体向上按设计不抖动」。**实测（`segment_thresholds` 全表逐档扫描，不是最小值）**：

| 组 | 阈值序列（前 8 个） | 档距 |
| --- | --- | --- |
| 男 大一、大二 | 6.7, 6.8, 6.9, 7.0, **7.1, 7.3, 7.5, 7.7** … 10.1 | 0.1 ×4，**0.2 ×15** |
| 男 大三、大四 | 6.6, 6.7, 6.8, 6.9, **7.0, 7.2, 7.4, 7.6** … 10.0 | 0.1 ×4，**0.2 ×15** |
| 女 大一、大二 | 7.5, 7.6, **7.7, 8.0, 8.3**, 8.5, 8.7 … 11.3 | **0.3 ×2**，0.1 ×2，**0.2 ×15** |
| 女 大三、大四 | 7.4, 7.5, **7.6, 7.9, 8.2**, 8.4, 8.6 … 11.2 | **0.3 ×2**，0.1 ×2，**0.2 ×15** |

即：20 个阈值里有 19 个档距，其中只有**最高 4 档**（100/95/90/85 分）是 0.1 s，其余 15 档是 **0.2 s**（女生另有 2 档 0.3 s）——是分辨率的**两倍**。控制者扫的是**最小**档距（表头就写着「最小档距」），而结论被表述成了「档距恰为 0.1 s」，两者不是一回事。

**后果**：`7.2 s` 这类读数是**合法的真实测量**（它与 7.3 s 同拿 80 分），真实高校的 50 米数据里必然大量存在，所以「50 米成绩全落在端点上」在这一项**同样是造的**，Ruling 54 的症状在这里成立、Ruling 57 的豁免不成立。而按 §4.2 的算法逐字实现（区间由相邻阈值定、整数单位、区间非空才抽数）时，这些档**必然**会抖——§4.1 的结论与 §4.2 的算法自相矛盾，不可能同时满足。

**我的处置（保守解释）**：以 §4.2 的**算法**为准，不为 50 米开特例。理由：① 算法是机械的、无例外的，加特例就要引入「哪些项豁免」的第二份知识；② Ruling 57 真正的规范内容是「**明令禁止生成 6.73 s 这类亚分辨率值**」，这一条我完全遵守——实测全部 50 米读数仍是 0.1 s 的整数倍（#3 断言）；③ 抖动值一律落在同档带内，得分不变，故**零算法后果**（Ruling 57 自己也承认「`score_item` 仍夹回同一档，算法后果同样为零」）。实测 500 人数据集里 42.2% 的 50 米记录不再是本组阈值（F2 表）。
**若控制者要的是「50 米一个字都不抖」**，需要给 `jitter_raw` 加一个按项的豁免集合（例如 `JITTER_EXEMPT_ITEMS`）——我没有自作主张加，请裁定。
**男生引体向上不受影响**：它的 14 个档距**处处等于**分辨率 1 次，Ruling 57 在这一处完全成立，实测恒不抖动，且已被 #4 的 `wide == 0` / `narrow == 30` 钉死。

#### 关切 B：简报 §3 与 progress.md 的「约 45% 的学生跨 19/20 线」不成立，实际是 26.4%

45% 是 `age >= 20`（本学年落在高龄组）的比例；真正**跨线**的判据是 `age_group_of(age) != age_group_of(age - 1)`，而 `age_group_of` 只有一个分界（19/20），故**只有 `age == 20` 跨线**。实测 500 人：132 / 500 = **26.4%**（年龄分布 18/19/20/21/22 = 132/143/132/80/13；`AGE_PROBABILITIES` 里 20 岁的权重是 0.25，故渐近值就是约 25%）。`age == 18` 的学生上学年 17 岁，`age_group_of(17)` 仍是「大一、大二」，**不跨线**。

缺陷本身是真的、也依然承重（1213 个单元格两表给出不同得分、趋势被低估 0.83 分/项，见 F1.2），但**量级要说对**：Task 9 若按 45% 估算受污染样本的比例，会把偏差的影响面高估约 1.7 倍。

附带一条：简报 §3 说「若两表对某生恰好全同，换一个跨线年龄再试」——**没有第二个跨线年龄可换**（只有 20 岁跨线）。我把可分辨性断言写成「所有跨线学生里至少有一个 (记录, 项) 单元格能分辨两张表」，实测 120 人配置下是 281 / 486 个单元格、27 / 27 名学生全部可分辨（500 人配置：1213 / 2376、132 / 132），远非空转。

#### 关切 C（**需要裁定**）：Ruling 55 的退化子句与实现相反，且字面公式在 n < 180 时自相矛盾

`administrative_section_count` 在 500 人下给出 14，与计划 Step 5 一致（F4）。但**退化分支不一致**，实测：

| n | 字面公式 `max(ceil(n/38), 6)` | 实现 | 实现下每班人数 | `[30,38]` 可行？ |
| --- | --- | --- | --- | --- |
| 40 | **6** | **2** | 20.0 | 否 |
| 120 | **6** | **4** | 30.0 | **是** |
| 180 | 6 | 6 | 30.0 | 是 |
| 500 | 14 | 14 | 35.7 | 是 |

计划 Step 5 / progress.md Ruling 55 / 简报 §2 三处都写「人数太少以致 `[30, 38]` 不可行时**退化为 `teachers × sections_per_teacher` 个班**且不施加下限」；实现恰恰相反——它在 `students // teacher_floor < low` 时**不抬**到教师下限，退回 `ceil(n / high)`（其 docstring 明写「反过来的方向……是不做的」）。

更要紧的是：**字面公式在 n < 180 时与它自己的班规模区间互斥**。n=120 时它给 6 个班 → 每班 20 人，直接违反「每班 30–38 人」；n=40 时给 6 个班 → 每班 6.7 人。也就是说 `max(ceil(n/high), teachers×spt)`、「每班 30–38 人」、以及 n<180 这三个条件不可能同时成立，与上一轮 Ruling 55 修掉的那个「12 × 38 = 456 < 500」是**同一类算术错误**，只是这次藏在退化分支里。而 n=120 恰好是 `[30,38]` **可行**的（4 × 30），实现给的 4 是唯一能同时满足「全员编入」与「每班 30–38」的班数——所以实现是对的，**计划那句退化子句是错的**。

按简报 §2「若发现不一致，上报，不要自行改」，我**未改任何代码与测试**。请裁定以哪一条为准：
- 若以实现为准（我的建议）：把计划 Step 5 的退化子句改成「退化为 `ceil(n / section_size_max)` 个班且不施加下限」，progress.md 的 Ruling 55 同步勘误；
- 若以计划为准：`administrative_section_count` 要改，且 `tests/seed/test_generate.py:431` 的 `4 + 3` 要改成 `6 + 3`，同时 120 人配置下每班 20 人，`test_administrative_section_size_within_bounds` 的适用范围要重新界定。

生产的 500 人配置在两种读法下都是 14 个班，故**本条不影响 Task 6 的任何输出**，只影响文档与两个测试配置的编班结构。

#### 关切 D：`sub_floor_rate` 的合法键口径——我收窄成 `Sex × WEAKNESS_ITEMS`（12 个），未按字面的 `Sex × ScoredItem`（14 个）

简报 §4.3 写「用到的键必须在 `Sex` × `ScoredItem` 的合法组合内」，字面含 `male:bmi` / `female:bmi`。但 BMI **不走反查**（`raw_from_score` 对它抛 `ValueError`）、也不出现在记录循环的反查分支里，接受 `male:bmi` 就等于留下一个**永远不生效却被判为合法**的键——与 §4.3 自己那句「静默忽略等于『配了但没生效』」直接冲突。故我把合法键定为 `Sex × WEAKNESS_ITEMS`，`*:bmi` 与任何拼错的键一律 `ValueError`（消息含全部 12 个合法键），并由 #10 的三个用例钉住（`male:no_such_item`、`female:bmi`、`bmi:male`）。
这是**从严**而非放宽：字面口径下合法的 14 个键里，我的实现接受同样的 12 个、多拒 2 个。若控制者认为应按字面 14 键，改 `sub_floor_marks` 里 `legal` 那一行 + 删掉 #10 的两个用例即可。**这是本轮唯一一处我对简报字面做的收窄，特此报备。**

#### 关切 E：简报 §4.4 #5 的「`jitter_within_band=False` 时全部原始值恰为端点」在默认 `sub_floor_rate` 下不成立

被标记男生的引体向上天然低于表内最低档（0–5 次），而 `raw_from_score` 对底档返回的是 5 / 6，两者不可能相等。故 #7 `test_jitter_can_be_disabled_by_config` 里我显式传了 `sub_floor_rate={}`（两个旋钮彼此独立，该条只量抖动）。**这不是放宽断言**：断言仍是全称等号（`checked == len(records) * len(WEAKNESS_ITEMS)`，一条不漏），只是把另一个旋钮关掉；若不关，那条测试量的就是「抖动 + 溢出都不生效」，反而与 #9 重复。若控制者希望「只关抖动、保留溢出」也有断言，可以再加一条排除 `pull_up_or_sit_up` 的用例——我没加，因为它会引入一个按项的例外，与 #9 的「六项全查」正好互补，价值有限。

#### 关切 F：脏数据注入的绝对计数变了，上一轮报告 §3 的那张对账表已过期

注入总数 1554 → **1572**（missing 1291→1318、outlier 173→173、duplicate 80→70、unit_error 10→11）；体测记录 3030 → **3035** 条；三个 CSV 哈希全变。原因是抖动与表下溢出在记录循环里消耗随机数，把 `inject_dirty` 之前（其实是之后——注入在三类数据生成完之后跑）的整条随机流平移了。这是**配置变更的预期后果，不是缺陷**：`test_injected_dirt_is_exactly_what_the_cleaning_layer_recognises` 仍全绿（两侧按 `(source, kind, field)` 完全相等），可复现性取证也已重做（F5.2）。但 Task 9 / Task 10 的派单若引用上一轮报告 §3 的具体数字（1554 / 1291 / 80、三个旧哈希、相关系数 0.533、桶均分 67.4），**请一律改用本轮 F5 的数字**。

#### 关切 G：`strength_count` 现在有两个语义不同的低值来源，Task 8/9 的「力量短板」判定会同时吃到

被标记者的 0–4（或 0–5）次是**表下溢出**（得分一律底档 10 分），未标记者的 5/6 次是**表内最低档**（得分同样是 10 分）。两者得分相同，但原始值语义不同：前者是「做不起 5 个」，后者是「刚好做得起 5 个」。若 Task 8/9 有任何逻辑按**原始值**（而不是得分）判力量短板，这两批人会被区别对待；若按**得分**判，则完全一致（实测被标记者与部分未标记者同为 10 分，男生引体向上得 10 分者共 28 人）。我按简报实现的是一律走 `score_item`，故生成器侧无歧义；此条纯粹是给 Task 8/9 的提示。

---

### F8. 前向约束（供 Task 8 / Task 9 派单使用）

1. **地板效应（承重，简报 §4.3 末尾要求写明）**：被 `sub_floor_rate` 标记的学生，该项得分被钉死在底档，故**该项的学年间趋势恒为 0**。实测 500 人 / seed=20250828 下 28 名男生的引体向上趋势集合 = `{0.0}`（28/28，无例外）。代码注释（`make_fitness_tests` 的表下溢出分支）与 #9 的 docstring 都已写明。
   - Task 8 的趋势判定：不得把「某项趋势为 0」当作「稳定」的正向证据来加权；若按「六项趋势一致下滑」判「持续下滑」，这 28 人天然少一项证据，判定阈值要能容忍缺一项。
   - Task 9 的黄金用例：涉及这 28 人的引体向上期望值一律是底档分（两个龄组都是 10），且**两学年相同**。
2. **「表内最低档」随龄组变**：男引体向上 大一二 = 5、大三四 = 6；女仰卧起坐 大一二 = 16、大三四 = 17。任何「低于表内最低档」的判定都必须按**该记录所属学年**的龄组算（Ruling 56），即 `min(segment_thresholds(table, item, sex, age_group_of(该学年的年龄)))`；用本学年龄组去判上学年记录会把 5 次误判成表下值。
3. **随机流的形状参数有三个**：`MEASURE_DECIMALS`、`sub_floor_rate`、`jitter_within_band`。Task 9 为命中 20/45/35 而调 `sub_floor_rate`（例如调到 0.15）时，会**同时改变所有列**的取值（记录循环里的抽数点变了），不只是 `strength_count`；调完必须重做可复现性取证（两次独立 CLI 进程 + 三个 CSV 哈希 + `seed=1` 差异性）。
4. **Task 9 的黄金用例期望值必须在本轮数据上重算**：就低取档（Ruling 18/22）+ 档内抖动 + 表下溢出 + 上学年按上学年龄组查表，四者叠加后的实际数据与上一轮**逐字节不同**。progress.md 里那条「不得沿用任何插值时期或端点时期的数值」在本轮之后范围更大。
5. **需要「纯端点」对照数据集时**：`SeedConfig(jitter_within_band=False, sub_floor_rate={})` 可精确退回上一轮的端点行为（#7 钉住「全部原始值 == `raw_from_score` 的端点」）。注意它仍与上一轮的字节**不同**，因为 Ruling 56 的龄组修正也生效了。
6. **力量维度的低尾已展开**：男生力量桶均分 65.65、sd 18.40、P25 57.00、最小 15.00（本学年 week1，n=275）；全员力量桶均分 67.4 → **66.51**。这与 progress.md 已记的那条非线性（μ=0 → 六项均值 67.5 而非 70）叠加，Task 9 调 `latent_mean` 时的起点变了，不得沿用旧起点线性外推。
7. **耐力/力量相关的余量变窄了一点点**：0.533 → **0.5211**，断言阈值 0.4 未动、余量仍充足。但若 Task 9 进一步调高 `sub_floor_rate`（把更多男生钉在底档），力量桶的方差会增大而相关性可能继续下降；调到某个点上 0.4 那条断言会真的失败，届时请按简报 §4.4 的规定**上报而不是私自改潜变量载荷**。

---

### F9. 本轮 git 输出

```
$ git log --oneline -1
34691f9 fix: 档内抖动与表下溢出使原始值脱离档位端点，上学年按上学年年龄组查表

$ git status --short
（无输出：工作树干净。backend/pe.db 与 backend/data/seed/*.csv 已由本轮 CLI 重跑刷新，
  两者均在 .gitignore 内，故不出现在此列表中——与上一轮的处置一致。）

$ git show --stat --oneline HEAD
 backend/app/seed/config.py          |  15 ++
 backend/app/seed/fitness.py         | 220 +++++++++++++++-
 backend/tests/seed/test_fitness.py  | 491 ++++++++++++++++++++++++++++++++++++
 backend/tests/seed/test_generate.py |   9 +-
 4 files changed, 721 insertions(+), 14 deletions(-)
```


---

## Fix Round 2

基线 `3b10f5e`（工作树干净）→ 本轮唯一 commit **`bed07ed`**（8 文件，+1579 / −119）。
测试 **236 → 280 passed**，`-W error` 同样 **280 passed**、输出洁净、**9.61 s**（普通模式 9.32 s）。
工作树提交后 `git status --short` 为空；`backend/pe.db` **自始至终不存在**（`Test-Path pe.db` = False，Ruling 68）。

落实范围：Ruling 62 / 63 / 64 / 65 / 66 / 69① + 4 条 Minor（m1/m2/m3/m4）。Ruling 67 / 68 是控制者已做的文档与库文件处置，本轮只在 G10 引用新数字。
简报 §4「明确不要做的事」逐条遵守：未实现 Task 8 的 `classify_trend` / `national_total` / `derive`；`app/domain/indicators.py` 只加了 `ITEM_WEIGHTS`（既有五个函数一字未改）；Ruling 54/55/56/57/58/60 的抖动、编班、龄组、表下溢出逻辑一字未动；未做二分法调参；未动 `write_csv` 三文件契约与 `allow_nan=False` / `make_batch_key` / 日期零填充；未加 `students.csv`；未拆 `generate.py`；4 条延后 Minor 未碰。

---

### G0. 改动清单（对照简报 §3）

| 裁定 | 落地位置 | 自证测试 |
|---|---|---|
| **Ruling 63** `ITEM_WEIGHTS` 与总分口径 | `app/domain/indicators.py:55-68`（新常量，和 100）；`app/seed/fitness.py` 私有 `_weighted_total` | `tests/domain/test_indicators.py` 4 条（字面值 / 键集合 / 和 100 / 六项和 85）+ `test_trend_oracle.py::test_weighted_total_is_the_floored_weighted_sum_of_seven_items` |
| **Ruling 62** 趋势符号 | `TREND_PROFILES` 字段 `prev_offset` → `delta_target_range` / `jitter` / `swing`；`prev_target = curr_i − delta_i`（`_settle_prev_targets`） | `test_trend_oracle.py::test_declining_group_really_declines_and_improving_group_really_improves`（**改动前红**，见 G1） |
| **Ruling 64** 判定表行序与阈值 | 生成侧 `_classify`（行序 波动大 → 持续下滑 → 稳步提升 → 稳定、命中即停；第二分支「≥3 项下降 ≥5 分」；`delta_i = 0` 两边都不计）；测试侧独立 `_oracle` | 10 条手算黄金用例 + 500 人全覆盖（G3） |
| **Ruling 65** 可构造性 | 均匀分配（`100·Delta_6 / w_free`）+ 零和整数抖动 `_zero_sum_jitter`；落档→重算→校正 `_settle_prev_targets`（上限 8 轮，超限 `RuntimeError`）；可行域配额 `_delta_target_windows` + `_trend_labels`（池不足 `ValueError`）；`make_fitness_tests` **拆成两趟**（`_anthropometrics` 先整批算身高体重与 BMI 得分） | `test_trend_oracle.py::test_all_four_labels_are_populated_and_volatile_has_the_required_shape`（波动大 == 75 且每人恰好 3 正 3 负 + `max|delta| ≥ 10`）、`test_fitness.py::test_trend_correction_loop_settles_every_student_within_the_round_cap` |
| **Ruling 66** `latent_sd` | `SeedConfig.latent_sd: float = 1.0`；`latent_profiles` 用它替代硬编码 `1.0` | `test_fitness.py` 3 条（字段存在且缺省 1.0 / 经验 sd 随 σ 变 / σ 传到三个桶潜变量） |
| **Ruling 69①** oracle | 新文件 `tests/seed/test_trend_oracle.py`（533 行、14 条） | 本身即测试 |
| **Minor m1** AST 守卫 | `test_generate.py`：判据改为「调用的**末段属性名**」+ 补 `Generator`/`PCG64`/`SeedSequence`/`RandomState`/`spawn`/`fork` | 20 条参数化自证测试 + 1 条负对照（G9.1） |
| **Minor m2** `_cell` | `generate.py:363` `repr(float(value))` + `np.integer` 分支 | `test_generate.py::test_cell_never_writes_a_numpy_scalar_repr_into_a_csv` |
| **Minor m3** docstring 撒谎 | `fitness.py:28-31` 改为「本模块自己不 open 任何文件；`app.seed` 里真正碰磁盘的是 `generate.write_csv` 与 `generate._ranges`」 | 全仓已无「唯一会碰磁盘」字样（`Select-String` 计数 0） |
| **Minor m4** `N(0, 0.6)` 记法 | 趋势抖动改为**有界零和整数**（正态记法随重写消失）；`LATENT_LOADINGS` 注释改写为「ε ~ 正态(均值 0, sd 0.6)」+ 字段注释 `(载荷, 残差 sd)` | 见 G11 关切 ⑥（计划 Step 3 的三行仍是 `N(0, 0.6)`，那是控制者的文档） |

新增测试 44 条：`ITEM_WEIGHTS` 4 + oracle 14 + AST 守卫自证 20 + 守卫负对照 1 + `_cell` 1 + 校正循环 1 + `latent_sd` 3 = 44；236 + 44 = **280**。`tests/seed` 由 35 条增至 **75** 条（`test_generate` 24→46、`test_fitness` 11→15、`test_trend_oracle` 0→14）。

---

### G1. 方向回归测试：改动前的失败输出（简报 §5.2 第 1 条）

**顺序**：先把 `ITEM_WEIGHTS` 与 `_weighted_total` 作为**纯新增**落盘（不改任何既有行为），再写 `test_trend_oracle.py`，此时跑出的红**只可能来自趋势方向本身**，不会混进 ImportError 之类的假红。改动前（基线 `3b10f5e` + 上述两处纯新增）：

```
$ cd backend; python -m pytest tests/seed/test_trend_oracle.py -q
...........FFF                                                           [100%]
================================== FAILURES ===================================
E   AssertionError: 309 名学生的 trend_label 与 spec §6.3 判定表不符（前 10 条：
    [(2, '持续下滑', '稳定'), (4, '稳步提升', '持续下滑'), (6, '稳定', '持续下滑'),
     (7, '波动大', '稳步提升'), (9, '稳步提升', '持续下滑'), (10, '稳步提升', '稳定'),
     (11, '持续下滑', '稳步提升'), (14, '持续下滑', '稳步提升'), (15, '持续下滑', '稳步提升'),
     (16, '稳步提升', '持续下滑')]）
    assert [(2, '持续下滑', ...', '稳定'), ...] == []
      Left contains 309 more items, first extra item: (2, '持续下滑', '稳定')
FAILED tests/seed/test_trend_oracle.py::test_oracle_agrees_with_trend_label_for_all_500_students
FAILED tests/seed/test_trend_oracle.py::test_declining_group_really_declines_and_improving_group_really_improves
  - AssertionError: 「持续下滑」组的加权总分变化中位数是 +8.0（应为负）：标签与数据方向相反
    assert 8.0 < 0
FAILED tests/seed/test_trend_oracle.py::test_all_four_labels_are_populated_and_volatile_has_the_required_shape
  - AssertionError: 波动大要求恰好 3 正 3 负，实际 (5, 0, 1)
    assert (5, 0, 1) == (3, 3, 0)
      At index 0 diff: 5 != 3
3 failed, 11 passed in 0.90s
```

三条红各自钉住评审的一个缺陷：**309/500 不一致** = C1 + M1；**「持续下滑」组中位数 +8.0（应为负）** = C1 的方向；**波动大 (5 正, 0 负, 1 零)** = C2。
同时 **11 条绿**（10 条手算黄金用例 + `_weighted_total` 的字面钉死），这证明 `_oracle` 本身是对的、红的是生成器而不是判据——否则「红」什么也证明不了。

改动后同一命令：`14 passed in 0.74s`。

> 口径说明：控制者 §2 那张诊断表用的是**六项之和（0–600）**，故「持续下滑」显示 +54.17；同一批人在**国标加权总分（0–100）**口径上是 **+8.0**。两个数字量的是同一个方向错误，只是分母不同（Ruling 63）。

---

### G2. 按国标加权总分口径（0–100）复算的四类分组表

`Delta = _weighted_total(本学年 week1 七项) − _weighted_total(上学年 week1 七项)`，`build_dataset(SeedConfig())`，seed=20250828，500 人。**正数 = 本学年更好**（Ruling 62）。

| 标签 | n | 均值 | 中位 | sd | min | max | 正数占比 | 负数占比 |
|---|---|---|---|---|---|---|---|---|
| 持续下滑 | 100 | **−8.17** | **−8.0** | 3.19 | −15 | −2 | **0.00%** | **100.00%** |
| 波动大 | 75 | +2.73 | +3.0 | 2.44 | −2 | +8 | 82.67% | 9.33% |
| 稳步提升 | 125 | **+14.26** | **+14.0** | 3.94 | +6 | +23 | **100.00%** | **0.00%** |
| 稳定 | 200 | +1.43 | +1.0 | 1.32 | −1 | +4 | 77.50% | 7.50% |

对照控制者 §2 那张诊断表（**修复前**、六项之和口径）：持续下滑 +54.17 / 正数占比 100%、稳步提升 −47.52 / 正数占比 0% —— 两类**完全互换**。修复后同一批人的六项之和口径是：

| 标签 | n | 均值(本−上) | 中位 | 正数占比 |
|---|---|---|---|---|
| 持续下滑 | 100 | **−57.05** | −60.0 | **0.00%** |
| 波动大 | 75 | +18.97 | +20.0 | 97.33% |
| 稳步提升 | 125 | **+99.92** | +100.0 | **100.00%** |
| 稳定 | 200 | +10.62 | +10.0 | 85.00% |

即：符号翻回来了，量级也与控制者那张表同阶（±54 / ±48 → −57 / +100）。六项之和口径下量级更大，是因为它不含 `//100` 的加权归一——**规格口径是上面那张 0–100 的表**，下面这张只用于与控制者的诊断数字直接对账。

**四类都非零方差、且「稳定」全部落在 `[−1, +4]`**（判据带是开区间 `(−5, +5)`，整数化后是 `[−4, +4]` 九个值，实测只用了其中六个）。

---

### G3. oracle 500 人全覆盖

| 项 | 值 |
|---|---|
| 配对成功的学生数 | **500 / 500** |
| `_oracle(实际 delta, 实际 Delta)` 与 `trend_label` 的**不一致数** | **0**（要求 0） |
| 四类人数 | 持续下滑 **100**、波动大 **75**、稳步提升 **125**、稳定 **200**（= `allocate_quota(trend_mix, 500)`，精确配额） |
| 对角命中率 | **500/500 = 100%**（修复前 59/500 = 11.8%） |

交叉表（行 = 生成器写的 `trend_label`，列 = 测试内独立实现的 `_oracle`）：

```
label\oracle    持续下滑   波动大   稳步提升    稳定   合计   对角
持续下滑              100       0        0      0    100    100
波动大                  0      75        0      0     75     75
稳步提升                0       0      125      0    125    125
稳定                    0       0        0    200    200    200
```

`Delta` 一律由 `_weighted_total` 从**记录里的 `score_bmi` 与六个 `score_*` 列**算出，不读生成器的任何中间变量（`Delta_target`、`prev_targets`、`bundle` 都没进测试）。`_oracle` 是**从 spec §6.3 的表格正文逐字翻译**的，四个字面阈值（3 / 10 / 5 / 3）写死在测试文件里、不从生成器或 Task 8 的常量导入；判定表那 11 条绿（G1）证明它自己是对的。

**波动大组 75 人的构造要求逐人成立**：`(正数项, 负数项, 零项) == (3, 3, 0)` 且 `max|delta_i| ≥ 10`，75/75。修复前是 1/75（评审 C2）。

---

### G4. 校正循环触发统计

`_settle_prev_targets` 返回的实测统计（monkeypatch 捕获生产路径的返回值，不是另写一份）：

| 项 | 值 |
|---|---|
| 参与构造的学生数 | **500** |
| **触发校正的学生数**（轮数 ≥ 1） | **19**（3.8%） |
| **最大迭代轮数** | **1** |
| 累计轮数 | 19 |
| 轮数分布 | `{0 轮: 481 人, 1 轮: 19 人}` |
| **`RuntimeError` 次数** | **0**（要求 0；上限是 `CORRECTION_MAX_ROUNDS = 8`） |

零注入配置下数字**完全相同**（19 / 最大 1 轮 / 0 次 RuntimeError）——注入发生在生成之后，不影响趋势构造。

**为什么触发率这么低、且最多一轮**：可行域筛选（G5）已经把「装不下该标签」的学生挡在池外，而落档损失是单向的（`prev_i ≤ prev_target` ⟹ `delta_i' ≥ delta_i`），所以只有「损失把 `Delta'` 推过判据线」这一种失配，一个官方档（w=20 的项推 10 分 → `Delta'` 动 2 分）就够修回来。8 轮的上限因此是**保守余量而不是实际需要**——但它必须留着：上限被撞到时的正确行为是响亮失败，不是静默放行。`test_trend_correction_loop_settles_every_student_within_the_round_cap` 里那条 `triggered > 0` 是**反空转守卫**：它证明量化损失确实会把人推出判据、循环不是死代码。

---

### G5. 可行域筛选的三个可行池

配额分配顺序 `波动大`（最受限）→ `持续下滑` → `稳步提升` → 余下给 `稳定`（计划 Step 4）。「顺序筛选后的池」= 轮到该类时**尚未被前面挑走**的可行人数，也就是实现里真正参与 `ValueError` 判定的那个数。

| 标签 | 需要 | 顺序筛选后的池 | 余量 | 全量可行人数（不受顺序影响） |
|---|---|---|---|---|
| 波动大 | **75** | **260** | 3.47× | 260 |
| 持续下滑 | **100** | **150** | 1.50× | 203 |
| 稳步提升 | **125** | **322** | 2.58× | 487 |
| 稳定 | **200** | 余下 **200** 人，其中稳定不可行 **0** 人 | — | 489 |

**最紧的是「持续下滑」（1.50×）**，因为它的判据同时要求 `head_up = min_i(100 − curr_i)` 够大（`prev_i` 要往上抬）**和**符号纯度（六项全负）。池不足会 `ValueError` 报出需要数与实有数，不静默改标签。

可行池的性别构成（500 人 = 男 275 / 女 225）：

| 标签 | 池 | 男 | 女 |
|---|---|---|---|
| 波动大 | 260 | 125（占男生 **45.5%**） | 135（占女生 **60.0%**） |
| 持续下滑 | 203 | 112（40.7%） | 91（40.4%） |
| 稳步提升 | 487 | 268（97.5%） | 219（97.3%） |
| 稳定 | 489 | 265（96.4%） | 224（99.6%） |

成因见 G11 关切 ②（`max curr ≤ 84` 这条判据对性别敏感：男生 `max(curr_i)` 的 p90 = 100、`≤84` 的比例 54.5%，女生 p90 = 98、比例 60.0%）。**实际分到的波动大组是 28 男 / 47 女**（人群是 275 男 / 225 女），即该类女生占比 62.7%。

---

### G6. 测试数与 `-W error`

```
$ cd backend; python -m pytest -q
280 passed in 9.32s

$ cd backend; python -m pytest -q -W error
......................................................................  [ 25%]
......................................................................  [ 51%]
......................................................................  [ 77%]
................................................................        [100%]
280 passed in 9.61s
```

**基线 236 → 280**（+44，逐条见 G0 末）。`-W error` 输出洁净：无 warning 摘要段、无 `warnings summary`、无 DeprecationWarning。既有 236 条**一条未改断言**——唯一被改动的既有测试是 `test_generators_thread_the_callers_rng_and_never_touch_the_clock`（守卫逻辑抽成 `_scan` / `_offenders_in` 以便自证测试能打它，`assert _scan(SEED_DIR) == []` 这条断言的强度未变），以及 `test_inject_dirty_leaves_clean_records_untouched_when_all_rates_are_zero`（**未动**，评审 m8 那条「末尾挂无关断言」属延后 Minor，简报 §4 明令不修）。

---

### G7. 可复现性取证（三个 CSV 的新 SHA256 前 16 位）

**取证方式偏离了简报字面，必须报告**：简报 §0 / §5.2 写「一律 `--out-csv` 到临时目录、不跑入库分支」，但 CLI 的 `main()` 是**无条件**「既写盘也入库」的（`generate.py:494` 起：`engine(DEFAULT_DB_URL)` → `init_db` → `seed_database` → `commit`），`--out-csv` 只改 CSV 路径、**不改入库行为**，而 `--reset` / `--db PATH` 按 Ruling 68 归 Task 11。所以「跑 CLI + `--out-csv`」与「不碰 `pe.db`」在当前代码上**互斥**。

我按简报的**意图**（不碰 `pe.db`）取证：写一个临时脚本直接调 `build_dataset(SeedConfig(...))` + `write_csv(ds, 临时目录)`，输出到 `%TEMP%\pe_hash_a` / `pe_hash_b` / `pe_hash_seed1`，**两次独立 Python 进程**各跑一遍。写盘路径与 CLI 逐字相同（同一个 `write_csv`），少掉的只是入库那一段（入库不改变 CSV 字节，`seed_database` 只写组织结构五张表，已由 `test_seed_database_writes_only_organisation_tables_and_is_idempotent` 钉住）。取证后临时目录与脚本已删除；`Test-Path pe.db` 全程 False。

| 文件 | 字节 | seed=20250828 进程 A | seed=20250828 进程 B | seed=1 |
|---|---|---|---|---|
| `fitness.csv` | 244496 | `498AA3256678B01A` | `498AA3256678B01A` | `11A6651B4CEA9A58` |
| `body_comp.csv` | 107745 | `1234025C05843B27` | `1234025C05843B27` | `242BE5A968C10594` |
| `survey.csv` | 276193 | `835A98FCC0779B51` | `835A98FCC0779B51` | `3245D2EAFEF7FA9D` |
| 目录内文件数 | — | 3（无 `students.csv`） | 3 | 3 |

两次独立进程三个哈希**逐一相同**；`seed=1` 三个文件**全部不同**。上一轮的 `35A0E49C…` / `0ECDDABA…` / `DAF36973…` **全部作废**（见 G11 关切 ⑤：它们还在工作区的 `backend/data/seed/` 里）。

---

### G8. 平移后的观测量新值（趋势重写平移了随机流，全部重测）

**相关系数与桶均分**（本学年 week1，500 人，缺省注入配置）：

| 量 | fix round 1 | **本轮** | 断言阈值 |
|---|---|---|---|
| corr(endurance, strength) | 0.5211 | **0.4954** | > 0.4（**一字未改**，余量 0.095） |
| corr(endurance, speedflex) | 0.4330 | **0.4260** | — |
| corr(strength, speedflex) | 0.3418 | **0.3188** | — |
| 桶均分 endurance | 67.62 | **67.81** | — |
| 桶均分 strength | 66.51 | **66.56** | — |
| 桶均分 speedflex | 67.62 | **68.00** | — |

**Ruling 54(a) 档内抖动**（零注入配置）：肺活量 **1801** 个不同取值（官方阈值并集 75 个；上一轮 1736）；非本组阈值的肺活量单元格占比 **95.1%**（上一轮 96.1%）。

**Ruling 54(b)/58 表下溢出**（零注入配置）：男生 **275** 人，标记 **28** 人（== `int(round(275 × 0.10))`，与上一轮同）；被标记者 **168** 条记录；`strength_count` 分布 **{0: 26, 1: 38, 2: 43, 3: 30, 4: 26, 5: 5}**（上一轮 {0:35, 1:28, 2:28, 3:32, 4:32, 5:13}）；按龄组 大一、大二 **126** 条 / 大三、大四 **42** 条（取值 5 只在后者，与上一轮同结构）；`score_pull_up_or_sit_up` 集合 = **{10}**（走 `score_item` 夹取，未写死）；`latent_strength` 被标记者最大 **−1.1447** < 未标记者最小 **−1.1196**（**与上一轮逐字相同**——Ruling 58 的选取只依赖 `latents`，而 `latent_profiles` 在随机流里的位置未变）；该项学年间趋势（week1）分布 **{0: 28}**（地板效应仍在）。

**Ruling 56 龄组**：跨 19/20 线的学生仍是 132/500 = 26.4%（只取决于 `make_population`，未受本轮影响）。`test_previous_year_records_use_the_previous_year_age_group` 的正确性半条与可分辨性半条都仍绿。

**趋势模型与表下溢出的协同**（简报 §3.2 第 6 点）：28 名被标记男生落在四类标签上是 **持续下滑 12 / 稳步提升 2 / 稳定 14 / 波动大 0**。波动大为 0 是**构造保证**的，不是巧合——被固定住的那一项 `delta ≡ 0`，既不计正也不计负，六项里最多只能凑出 3 正 2 负，`min(3,2) = 2 < 3` 永远命中不了第一行。`_delta_target_windows` 因此把 `len(free) == 6` 加进了波动大的判据（见 G11 关切 ②）。

---

### G9. 四条 Minor 的修法与各自的自证测试

#### G9.1 m1 — AST 随机源守卫补两种写法（+ 每一种被禁写法的自证测试）

**修法**：`test_generate.py` 里把守卫逻辑抽成模块级的 `_offenders_in(filename, source)` 与 `_scan(root)`，判据从「7 个精确串」改成「**调用的末段属性名**」：

```python
head = ast.unparse(node.func).rsplit(".", 1)[-1]
if head == "default_rng":
    if filename != "generate.py" or not node.args: offenders.append(...)   # 唯一合法入口
elif head in RNG_SOURCES: offenders.append(...)                            # 自己造生成器/播种/派生子流
if head in CLOCK_METHODS: offenders.append(...)                            # 时钟
```

`CLOCK_METHODS = {today, now, utcnow, time, monotonic, perf_counter}`；`RNG_SOURCES = {RandomState, Generator, SeedSequence, seed, PCG64, PCG64DXSM, MT19937, Philox, SFC64, spawn, fork}`。末段属性名**与导入别名无关**，所以评审 m1 点名的三种绕道（`import datetime` 后的 `datetime.datetime.now()` / `datetime.date.today()`、以及 `Generator(PCG64(...))`）现在一律抓住；`dt.datetime.now()` 这类原有写法也仍然抓住。

**自证测试**：`test_the_random_source_guard_catches_every_forbidden_writing` 参数化 **20 种**被禁写法，每一种都在 `tmp_path` 下写一个假模块 `fake_module.py`，断言 `_scan(tmp_path)` 非空**且**至少一条 offender 指向预期 token：

`import random` / `from random import Random` / 无种子 `default_rng()` / 非 generate.py 的**带种子** `default_rng(seed)` / `np.random.seed` / `RandomState` / `np.random.Generator(np.random.PCG64(0))` / `from numpy.random import Generator, PCG64, SeedSequence` + `Generator(PCG64(SeedSequence(0)))` / `rng.spawn(1)` / `rng.fork(1)` / `dt.datetime.now()` / `datetime.datetime.now()` / `datetime.now()` / `datetime.utcnow()` / `dt.date.today()` / `datetime.date.today()` / `date.today()` / `time.time()` / `time.monotonic()` / `time.perf_counter()`。

**负对照**：`test_the_guard_allows_the_single_seeded_root_generator` 在 `tmp_path/generate.py` 里写「带种子的 `default_rng(cfg.seed)` + `Generator` 只作类型标注 + `cfg.seed` 只作属性读取 + `timepoint_date(...)`」，断言 `_scan(tmp_path) == []`。没有这条，20 条自证测试全绿也可能只是因为守卫「见 `ast.Call` 就报」——一个永远报警的守卫与一个永远沉默的守卫同样无用。

`_scan` 开头保留 `assert root.is_dir()`（Ruling：目录缺失时空转全绿是本项目踩过的坑）。

#### G9.2 m2 — `_cell` 对 numpy 标量写坏单元格

**修法**：`generate.py` 的 `_cell` 里 `return repr(value)` → `return repr(float(value))`，并新增 `if isinstance(value, np.integer): return int(value)`。`np.float64` 是 Python `float` 的子类故会进 `repr` 分支，而 numpy 2.x 下 `repr(np.float64(1.5)) == 'np.float64(1.5)'`——那种字符串会原样落进 CSV，适配器 `float()` 解析时抛 `ValueError` 并中断**整批**抽取。

**自证测试**：`test_cell_never_writes_a_numpy_scalar_repr_into_a_csv` 走**完整落盘路径**（把 `fitness` 的八个测量列全换成 `np.float64` / `strength_count` 换成 `np.int64` → `inject_dirty` → `write_csv` → 读回 CSV 文本），断言文本里既无 `np.float64(` 也无 `np.int64(`；外加四条直接断言 `_cell(np.float64(1.5)) == "1.5"`、`_cell(np.float64(-0.3)) == "-0.3"`、`_cell(np.int64(7)) == 7`、`"np.float64(" not in repr(...)`。之所以不只调一次 `_cell`：`_damage` 里 `round(np.float64(...) / 100, 3)` 会**保持** numpy 类型，那才是最容易漏包 `float()` 的路径，必须端到端走一遍。

#### G9.3 m3 — `fitness.py:28` docstring 撒谎

**修法**：模块 docstring 末段改为「**本模块自己不 open 任何文件**：需要国标评分表时只经 `app.refdata.standard()` 这个受管加载器取……`app.seed` 里真正碰磁盘的是 `generate.write_csv`（写三个 CSV）与 `generate._ranges`（经 `load_ranges` 读 `indicator_ranges.yaml`）」。全仓已无「唯一会碰磁盘」字样（`Select-String -SimpleMatch` 计数 0）。
**自证**：这条是文档更正，没有可断言的运行时行为；它的守卫是评审 m3 自己用的那条命令（`git grep -nE "open\(|read_text|read_csv" -- backend/app/seed` 只命中 `generate.py`），本轮未新增测试——按简报「不做未要求的事」，不为一句 docstring 造一条测试。

#### G9.4 m4 — `N(0, 0.6)` 记法

**修法**：两处。(a) 趋势模型里唯一的正态抖动 `rng.normal(0.0, ITEM_TREND_JITTER_SD)` 连同 `ITEM_TREND_JITTER_SD` 一起**删除**，改成 `_zero_sum_jitter`：`rng.integers(-bound, bound+1, size=n)` 抽**有界整数**再削成零和——既没有「方差还是标准差」的歧义（`integers` 的参数是界不是尺度），也满足计划要求的「和为零」。(b) `LATENT_LOADINGS` 的注释从 `endurance = 0.8·fitness + N(0, 0.6)` 改写成 `endurance = 0.8·fitness + ε，ε ~ 正态(均值 0, sd 0.6)`，并在字典第一行加 `# (载荷, 残差 sd)`。
**自证测试**：`test_latent_sd_propagates_through_the_bucket_loadings` 用**手算的理论值**钉住 sd 语义——`sd(endurance) = sqrt(0.8²·σ² + 0.6²)`，σ=1 时 1.0 / 0.9899 / 1.0，σ=2 时 1.7088 / 1.5524 / 1.4422，各 ±0.15。**若有人把这三个数按方差读**（`rng.normal(0, 0.6)` 当成方差 0.6 即 sd 0.775），σ=1 时 endurance 的经验 sd 会变成 `sqrt(0.64+0.6)=1.113`、σ=2 时 `sqrt(2.56+0.6)=1.778`——后者仍在带内，但前者会因 strength 的理论值从 0.9899 变成 1.1045 而超出 ±0.15 的带宽（1.1045 vs 0.9899 差 0.115，在带内）……**这条测试对「方差读法」的分辨力不足**，见 G11 关切 ⑦。

---

### G10. Ruling 67 / 68 的新数字（控制者已做，本轮只引用）

* **Ruling 67**：Ruling 56 的影响面是 **334 / 2376 个上学年单元格（14.1%）、103 / 132 名可分辨学生**，不是 `1213 / 2376（51.1%）`。本轮未重测这个量（它量的是**修复前**代码的缺陷面，而 Ruling 56 的修复本轮一字未动）；`test_previous_year_records_use_the_previous_year_age_group` 的可分辨性半条（`discriminative > 0`）仍绿。
* **Ruling 68**：`backend/pe.db` 已被控制者删除，本轮**全程未创建**（`Test-Path pe.db` = False，取证走临时目录，见 G7）。但 `backend/data/seed/*.csv` **仍在工作区里**，且内容是 fix round 1 的旧产物——见 G11 关切 ⑤。

---

### G11. 关切

> 按简报 §0 的要求逐条上报，不静默绕过、也不自作主张改设计。①③⑥⑦ 是**简报/计划的文字与事实不符**，②④⑤⑧⑨ 是实现过程中发现的、需要控制者裁定的事实。

**① 计划 Step 4 的可行域判据在「均匀分配」下不成立（我已按简报 §6.1 第 1 条授权收紧）。**
计划写：`持续下滑` 需要 `Σ_i w_i·(100 − curr_i) ≥ 100·|Delta_target|`、`稳步提升` 需要 `Σ_i w_i·curr_i ≥ 100·Delta_target`。这两个都是**加权和**判据。但同一页的分配方式是**均匀**的（每项承担 `100·Delta_6 / 85`），于是真正卡住构造的是**逐项最小余量**：`min_i(100 − curr_i) ≥ |d| + jitter + 校正预留`。加权和够大并不蕴含逐项够大——具体反例：某生 `curr = (95, 95, 95, 95, 95, 20)`，`Σ w_i(100 − curr_i) = 15×5 + 20×5 + 10×5 + 10×5 + 10×5 + 20×80 = 1925 ≥ 1800 = 100×|−18|`，**通过计划的判据**；但均匀分配要每项都降 `100×18/85 ≈ 21.2` 分，而前五项只有 5 分余量，`prev_target` 会冲到 105、被夹到 100 后 `delta' = −5`，校正循环再往上推已经推到表顶端点档、**推不动 → RuntimeError**。
我的处置：按简报 §6.1 第 1 条「先怀疑可行域筛选，把判据收紧再试」，改用 `min_i` 形式（`_delta_target_windows` 的 docstring 里写明了这是对计划正文的收紧及理由）。实测后果：持续下滑的全量可行池 203/500、顺序筛选后 150（需 100，余量 1.50×），**0 次 RuntimeError**。
**这与 Ruling 55 / 59 / 61 / 67 是同一类错误**（一个聚合量被当成了逐项量），建议更正计划 Step 4 那两句。若判断错：判据偏严只是让池变小，池不够会响亮 `ValueError`，不会静默产出错数据。

**② 「波动大」的可行域判据必须排除被表下溢出标记的学生，计划与简报都没写。**
计划给的判据只有 `min curr ≥ 16 且 max curr ≤ 84`。但被 Ruling 58 标记的学生其 `pull_up_or_sit_up` 的 `delta ≡ 0`（地板效应），而 §14 #23 明写 `delta_i = 0` **既不计入正也不计入负**，于是六项里最多只能凑出 3 正 2 负（或 2 正 3 负），`min = 2 < 3`，**波动大对这些人结构性不可达**。若不排除，他们会被分进波动大池、然后在校正循环里怎么推都命中不了判据 → RuntimeError（因为符号分裂是构造出来的，不是幅度问题）。
我的处置：判据加 `len(free) == 6`（`_delta_target_windows`）。实测 28 名被标记男生**全部**被排除，波动大组 0 人来自他们（G8 末）。
**附带一个需要控制者知道的分布后果**：波动大的判据 `max curr ≤ 84` 对性别敏感——男生 `max(curr_i)` 的 p90 = 100、`≤84` 的比例 54.5%，女生 p90 = 98、比例 60.0%；叠上 28 名男生被整条排除，波动大可行池是 男 125/275（45.5%）vs 女 135/225（60.0%），**实际分到的 75 人是 28 男 / 47 女**（女生占 62.7%，而人群里女生只占 45%）。趋势类别因此带性别偏斜。规则 Y4 只看「持续下滑」（其可行池性别比是 40.7% vs 40.4%，基本平衡），故对 Y4 的直接影响小；但 Task 9 若按性别分层看趋势分布，会看到这个偏斜。这是可行域判据的必然后果，不是缺陷，我没有去「修平」它（那需要按性别分别设配额，超出简报范围）。

**③ 计划 Step 4 第 3 步的 `Delta' = Σ w_i·delta_i' / 100（整数运算，无隐藏误差）` 两处都不对，我用了另一个口径。**
(a) 它不是整数运算：`/100` 是真除法，`Σ w_i·delta_i' = −250` 时 `Delta' = −2.5`。
(b) 它与**实际被判定使用的量**不是一回事。`national_total`（Task 8）与 `_weighted_total`（本轮）都是 `Σ w_i·score_i // 100`（向下取整），所以 oracle 与 Task 8 判的是 `(Σw·curr)//100 − (Σw·prev)//100`，与 `Σ w_i·delta_i' / 100` 相差最多 1 分。具体反例：`Σw·prev = 7500`（总分 75）、`Σ w_i·delta_i' = −480` → `Σw·curr = 7020`（总分 70）→ **整数口径 `Delta = −5`（触发持续下滑第一分支）**，而计划口径 `−4.8`（**不触发**）。稳定类的可行带只有 `[−4, +4]` 九个整数，1 分之差足以让同一个学生在生成侧被判「达标」、在 oracle 侧被判「不达标」。
我的处置：校正循环里的 `Delta'` 一律用 `_weighted_total(curr) − _weighted_total(prev)`（`_settle_prev_targets` 的 docstring 写明了理由）。**实测这个差异是真实存在的但本轮没有翻面**：500 人里 `floored − continuous` 非零的有 **443 人**（分布 min −0.90 / max +0.95 / mean +0.024），而两种口径给出**不同分类**的是 **0 人**。0 是这一份数据的运气，不是构造保证——所以我按整数口径实现。
建议更正计划那一句（并把简报 §3.3 的示例算式 `= −250 → Delta = −2.5` 改成 `→ 上学年 75、本学年 72、Delta = −3`，见关切 ⑦）。

**④ 「稳定」类有一个 +1.40 分的系统性上偏，四类都有（这是就低取档的必然后果，不是缺陷，但 Task 9 需要知道）。**
`prev_i = 不超过 prev_target 的最大官方档 ⟹ prev_i ≤ prev_target ⟹ delta_i' ≥ delta_i`，量化损失是**单向**的，故实际 `Delta'` 一律 ≥ 名义 `Delta_target`。实测（名义均值 → 实际均值，平均偏差）：

| 标签 | 名义 `Delta_target` 均值（区间） | 实际 `Delta'` 均值（区间） | 平均偏差 |
|---|---|---|---|
| 持续下滑 | −9.92（[−17.48, −6.03]） | −8.17（[−15, −2]） | **+1.75** |
| 稳步提升 | +12.15（[+6.05, +17.76]） | +14.26（[+6, +23]） | **+2.11** |
| 稳定 | +0.03（[−1.92, +1.98]） | +1.43（[−1, +4]） | **+1.40** |

后果：稳定组 77.5% 的人 `Delta'` 为正、均值 +1.43（「稳定」的人在轻微进步）；持续下滑组的实际降幅只有名义的 82%。**上界值得单独说**：持续下滑组的 `Delta'` 最大是 **−2**，也就是有人总分只降了 2 分却被标为持续下滑——他靠的是判据的**第二分支**（≥3 项各降 ≥5 分），完全符合 spec §6.3，但意味着「持续下滑」这一类在总分维度上**不同质**。Task 9 校准 20/45/35 时若按总分分布反推 Y4 的触发面，会低估它。

**⑤ `backend/data/seed/*.csv` 仍在工作区里，且是 fix round 1 的旧产物（Ruling 68 的删除只落到了 `pe.db`）。**
实测：三个文件的时间戳是 **2026-09-29 22:23:29**（早于本轮我跑的任何命令），SHA256 前 16 位是 `fitness 35A0E49CB118DB55` / `body_comp 0ECDDABA7531817A` / `survey DAF36973A0DA49D6`，字节 244723 / 107559 / 275640 —— 与 `progress.md:649` 记的 fix round 1 三个哈希**逐一相同**。而本轮的产物是 `498AA325…` / `1234025C…` / `835A98FC…`（G7）。`Test-Path pe.db` = False，说明 `pe.db` 确实被删了、CSV 没有。
**我没有删它**：不是我造的，且删除是不可逆操作。它在 `.gitignore:20` 内，不影响本轮提交（`git status --short` 为空）。但 Task 10 若直接消费 `backend/data/seed/`，会读到**两轮之前**的数据、且读起来完全合法（三个文件、列序对、日期对），没有任何一处会报错。请控制者决定是删掉还是用本轮的产物覆盖。

**⑥ 简报 §3.5 第 4 条把 `N(0, 0.6)` 记法归到 `TREND_PROFILES`，实际它在 `LATENT_LOADINGS`；而计划 Step 3 的那三行我按 §4 没动。**
`TREND_PROFILES` 从来没有 `N(0, 0.6)`（它只有 `prev_offset` 与 `drift_scale`）。含正态记法的是两处：`LATENT_LOADINGS` 的注释（`fitness.py:68-72`）与 `_trend_offsets` 里的 `rng.normal(0.0, ITEM_TREND_JITTER_SD)`。我按最能满足意图的方式做了：后者随重写**整体删除**（改成有界零和整数抖动，见 G9.4），前者的注释改写成显式 `sd`。
但**评审 m4 的建议是「把计划 Step 3 的三行改成 `N(0, 0.6²)` 或明写括号内是标准差」**，那三行现在仍在 `Document/2026-09-28-实施计划01-数据基座与分层引擎.md:876-878`。我没改——简报 §4 明令「不做本简报未要求的重构」，且改计划/规格按本项目的规矩必须由控制者做。请控制者补这一处，否则 Task 9 的读者拿计划对代码仍会对不上。

**⑦ 我给 m4 写的那条自证测试，对「把 sd 当方差读」这个具体失效模式的分辨力不足——报告出来，不掩饰。**
`test_latent_sd_propagates_through_the_bucket_loadings` 用理论值 ±0.15 钉住 sd 语义。但按方差读（`sd = sqrt(0.6) = 0.775` 等）时，σ=1 的三个理论值会从 1.0 / 0.9899 / 1.0 变成 1.1135 / 1.0440 / 1.0770，**都还落在各自 ±0.15 的带内**；σ=2 时是 1.7776 / 1.6000 / 1.5232，也都在带内。也就是说这条测试能证明「σ 接到了桶潜变量上」（这是它的主要目的，Ruling 66），但**证明不了「残差按 sd 读而不是按方差读」**。真正钉住后者的是既有的 `test_indicator_correlation_is_realistic`（`corr > 0.4`）：按方差读会让它从 0.4954 掉到 0.46 附近，余量只剩 0.06。
我没有为此再加一条测试（那需要在测试里重算相关系数的理论值，成本高于收益，且简报没要求）。如果控制者认为 m4 需要一条真正的守卫，最小改法是把带宽从 ±0.15 收到 ±0.05——但那会让它对换种子敏感（500 人下抽样波动约 0.05），我不建议。**这是我在本轮唯一一处明知不足而没有补强的地方。**

**⑧ Task 8 的对账测试（Ruling 69②）不能用缺省注入配置，否则会与 `trend_label` 不符——原因与趋势模型无关。**
简报 §3.3 要求我用 `build_dataset(SeedConfig())`（含缺省注入），我照做了，500/500 一致。能一致的原因是：`inject_dirty` 只改**测量列**、不回算 `score_*` 列（上一轮已裁定的设计），而我的 oracle 读的是 `score_*` 列。
但 Task 8 的生产侧对账必须从**清洗后的原始值重新正查得分**（那是 `national_total` / `classify_trend` 的真实输入）。在那条路径上：4% 的 `missing` 注入会让某个 `score_i` 变成 `None` → `national_total` 返回 `None` → `classify_trend` 走 `INSUFFICIENT` 分支；0.5% 的 `outlier` 注入会把得分夹到边界、凭空造出 ±大 delta；1% 的 `duplicate` 会让 `(student_id, academic_year)` 配对出现两行。**这些都会让对账测试红，而红的原因与趋势模型无关。**
建议写进 Task 8 的派单：对账测试用 `SeedConfig(dirty={...全 0...})`，或沿用 `test_generated_raw_values_roundtrip_through_the_official_table` 里那套现成的 `dirty_marks` 过滤写法（按 `(学号, 列)` 跳过被注入的单元格）。我这一侧的 oracle 测试已在 fixture 的 docstring 里写明了这个前提。

**⑨ 趋势判据只在 `week1` 上被构造保证；`week8` / `week16` 的学年配对实测有 4–5% 不一致。**
上学年三个时点的目标分是 `prev_target(week1) + drift[slot]`，本学年是 `targets + drift[slot]`——**目标空间**里的学年差在三个时点上是同一个 `delta_i`。但两个学年各自还要**再落档一次**，而落档是阶梯函数，`drift` 一变、量化损失就变，于是 `delta_i'` 随时点漂移（单项最多 ±9）。实测（同一份数据、同一个 `_oracle`）：

| 配对时点 | 不一致人数 | 逐类命中 |
|---|---|---|
| **week1** | **0 / 500** | 100/100、75/75、125/125、200/200 |
| week8 | 25 / 500（5.0%） | 持续下滑 89/100、波动大 72/75、稳步提升 124/125、稳定 190/200 |
| week16 | 21 / 500（4.2%） | 持续下滑 95/100、波动大 71/75、稳步提升 125/125、稳定 188/200 |

计划 `:1196` 给 Task 8 的对账测试写的正是「配对两学年的 **week1** 记录」，口径一致，**当前无需处置**。但要写进 Task 8/10 的派单：若将来改用 week16 配对（或跨时点配对，例如本学年 week16 vs 上学年 week1），`trend_label` 会有 4–5% 对不上，那不是缺陷而是构造边界。要消除它得让三个时点共用同一次落档结果（即先把 `prev_i` / `curr_i` 定死、再让 `drift` 只作用于原始值不作用于得分），那是比本轮大得多的改动，我没有做。

---

### G12. 前向约束（新增 / 更新，请并入 Task 8 / 9 / 10 / 11 派单）

1. **`_weighted_total` 应在 Task 8 删除、改用 `national_total`**（`app/seed/fitness.py`，docstring 已写明）。它是私有的、不在 `app.seed` 的公开面上，但**它现在是仓里第二处加权求和**。Task 8 落地后必须：把 `_weighted_total` 的调用点改成 `derive.national_total`、删掉该函数、并把 `tests/seed/test_trend_oracle.py` 里那条 `test_weighted_total_is_the_floored_weighted_sum_of_seven_items` 改成钉 `national_total`（期望值可以逐字搬过去，它们同口径）。生成侧的 `_classify` 同理应改为调用 `derive.classify_trend`（届时 Ruling 69② 的对账测试会把三方钉在一起）。
2. **`ITEM_WEIGHTS` 是全仓唯一的权重所有者**（`app/domain/indicators.py`）。Task 8 的 `national_total`、Task 10 的 `fitness_test_result.total_score`、Task 9 的任何总分口径一律读它，**不得手抄第二份**、也不得在测试里手写 `sum(w*v)//100`（唯一例外是 `test_item_weights_match_spec_4_2_verbatim`，它必须写字面值才能钉住 spec §4.2）。
3. **四类标签修好后，Y4 的触发人群会大幅变化**：修复前 46%（230/500）被判持续下滑，修复后是**精确的 20%（100/500）**，即配置的 `trend_mix`。Y4 = `W=0 AND NOT C AND 趋势=持续下滑 → yellow`，其候选人群因此缩小到原来的 **43%**。Task 9 的 20/45/35 校准**必须在本次数据上重做**，`progress.md` 里本轮之前的所有分层相关实测数字一律作废。另见 G11 关切 ④：持续下滑组在总分维度上不同质（`Delta'` 从 −15 到 −2），按总分反推 Y4 触发面会低估它。
4. **随机流的形状参数清单增至六个**：`MEASURE_DECIMALS` / `sub_floor_rate` / `jitter_within_band` / **`latent_sd`**（Ruling 66 新增）/ **趋势模型的幅度常量**（`TREND_PROFILES` 的 `delta_target_range`、`jitter`、`swing`，以及 `CORRECTION_STEP`）/ **`make_fitness_tests` 的两趟调用顺序**（本轮新增的形状参数：`_base_targets` → `_anthropometrics` → `_trend_labels` → `_within_year_drifts` → `_trend_prev_targets` → 记录循环）。改其中任何一个都会改变**所有列**的字节，须重做可复现性取证（两次独立进程 + 三个 CSV 哈希 + `seed=1` 差异性）。
5. **趋势判据只在 week1 上成立**（G11 关切 ⑨ 的实测数字）。Task 8 的对账测试必须配对两学年的 **week1**；Task 10/11 若在演示里展示「学年对比」，也应用 week1，否则会有 4–5% 的学生标签与数据对不上。
6. **Task 8 的对账测试不能用缺省注入配置**（G11 关切 ⑧）：用零注入，或按 `dirty_marks` 跳过被注入的 `(学号, 列)`。
7. **地板效应现在与趋势模型显式协同**：被 Ruling 58 标记的学生，其 `pull_up_or_sit_up` 不参与 `delta_i` 的分配（只在其余五项上均匀分配，分母是 `w_free = 75` 而不是 85），且该项的 0 贡献被算进 `Delta'`。**他们永远不会被标为「波动大」**（G11 关切 ②）。Task 9 的黄金用例若挑到被标记的学生，须容忍：五项有趋势、一项恒为 0。
8. **`latent_sd` 是 Task 9 的第二个旋钮**（Ruling 66）。它与 `latent_mean` 一起决定红层规模；改它会平移随机流（G12 第 4 条），调完必须重做可复现性取证。本轮**未做**二分法调参。
9. **`backend/data/seed/*.csv` 是 fix round 1 的旧产物**（G11 关切 ⑤）。Task 10 派单前必须删掉或用本轮产物覆盖，否则会静默消费两轮之前的数据。
10. **可行域判据比计划正文更严**（G11 关切 ①）。Task 9 若调 `latent_mean` / `latent_sd` 把人群整体推高（`max curr` 普遍 > 84），**波动大的可行池会先枯竭**（现在 260/500，判据是 `max curr ≤ 84`），届时 `make_fitness_tests` 会抛 `ValueError` 报出需要数与实有数——那是设计行为，不要把它当成 bug 去放宽判据；正确做法是同步调 `TREND_PROFILES["波动大"].swing` 的上限或调 `trend_mix`。

---

### G13. 本轮 git 输出

```
$ git log --oneline -1
bed07ed fix: 重写趋势模型使其满足 spec 6.3 判定表，补 ITEM_WEIGHTS 与 oracle 测试

$ git status --short
（无输出：工作树干净。backend/pe.db 全程未创建（Ruling 68）；backend/data/seed/*.csv 是
  fix round 1 的遗留、在 .gitignore:20 内，故不显示——见 G11 关切 ⑤。
  .superpowers/ 在 .gitignore 内，本报告与账本本来就不进版本库。）

$ git show --stat --oneline HEAD
 backend/app/domain/indicators.py        |  14 +
 backend/app/seed/config.py              |   6 +
 backend/app/seed/fitness.py             | 750 ++++++++++++++++++++++++----
 backend/app/seed/generate.py            |  10 +-
 backend/tests/domain/test_indicators.py |  47 +-
 backend/tests/seed/test_fitness.py      | 115 +++++
 backend/tests/seed/test_generate.py     | 223 +++++++--
 backend/tests/seed/test_trend_oracle.py | 533 +++++++++++++++++++++++
 8 files changed, 1579 insertions(+), 119 deletions(-)
```

临时探针文件（`backend/_tmp_probe_trend.py`、`backend/_tmp_probe_hash.py`、`backend/_tmp_probe_concerns.py`）与三个临时 CSV 目录（`%TEMP%\pe_hash_a` / `pe_hash_b` / `pe_hash_seed1`）**已全部删除**，`Test-Path` 逐一复核为 False。

---

## Fix Round 3

基线 `1fbc35f` → 本轮 commit **`945877f`**（**一个** commit）。范围严格照简报 §2：复审 Minor-1（AST 守卫漏 `np.random.*`）、Minor-2（`_cell` 漏 `np.floating`）、Minor-4（四条响亮失败守卫零覆盖）三条必修 + Minor-7 的注释。复审明确延后的三条（`_correction_move` 的 0 命中分支、m4 自证测试的分辨力、窗口公式本身）**一条未碰**。

### H0. 结论速览

| 项 | 值 |
|---|---|
| 测试数 | **280 → 310**（+30） |
| `pytest -q`（在 `backend/` 下） | **310 passed in 10.02s** |
| `pytest -q -W error` | **310 passed in 9.69s**，**洁净**（输出里没有 warnings 段） |
| 既有 280 条的断言 | **一条未改、未放宽**（见 H0.1） |
| 三个 CSV 的 SHA256 前 16 | **逐字未变**（见 H1） |
| 生成逻辑改动 | **0 行**（见 H0.2） |
| `backend/pe.db` | 全程未创建（每次取证后 `Test-Path` 复核为 `False`） |
| `backend/data/seed/` | 全程保持**空目录**（0 个文件）；取证一律写 `%TEMP%` |
| 新增测试的分布 | `test_generate.py` 46 → **70**（+24）；`test_fitness.py` 15 → **21**（+6） |

+30 的构成：22 条 AST 守卫参数化用例（每种新增禁用写法一条）+ 1 条 AST 负对照 + 1 条 `_cell`（`np.floating` 全 dtype + 端到端）+ 6 条守卫自证（`:805` 两个方向 2 条、`:813` 1 条、`:606` 1 条、`:618` 1 条、真实 `SeedConfig` 走 `build_dataset` 1 条）。

#### H0.1 「既有断言一条未改」的取证

`git show HEAD --unified=0` 里**全部 7 行删除**如下，没有一行是断言：

```
-    if isinstance(value, float):                                       ← generate.py，被换成 (float, np.floating)
-    全局状态写法、任何「自己造一个 Generator」的写法、任何 ``import random`` 都算违规。   ← 守卫测试的 docstring（扩写）
-    **判据本身由下面两条测试双向钉住**：…                              ← 同上（两条 → 三条）
-    评审 Minor m1）；:func:`test_the_guard_allows_the_single_seeded_root_generator` 是负对照。  ← 同上
-    for node in ast.walk(ast.parse(source)):                           ← _offenders_in 重排（先扫导入表）
-            if (node.module or "").split(".")[0] == "random":           ← 同上（补 numpy.random 分支）
-                offenders.append(f"{filename}:from {node.module}")      ← 同上
```

即：**没有任何一条既有 `assert` 被删除、改写、加容差、或把全称量词换成存在量词**。

#### H0.2 「不改生成逻辑」的取证

`git show HEAD --unified=0 -- backend/app/seed/fitness.py` 过滤掉注释行后**输出为空**——`fitness.py` 那 45 行改动**全是注释**（Minor-7 要求的那一段）。`generate.py` 的代码改动只有 H0.1 里那一行判据。H1 的三个哈希逐字未变是这条的硬证据。

---

### H1. 可复现性取证：三个 CSV 的 SHA256 **逐字未变**

**结论：三个哈希与简报要求的值逐字相同，两次独立进程一致，字节数也与复审时相同。本轮没有动到任何不该动的东西。**

| 文件 | 要求的前 16 位 | 进程 A | 进程 B | 字节 | 一致 |
|---|---|---|---|---|---|
| `fitness.csv` | `498AA3256678B01A` | `498AA3256678B01A` | `498AA3256678B01A` | 244496 | ✓ |
| `body_comp.csv` | `1234025C05843B27` | `1234025C05843B27` | `1234025C05843B27` | 107745 | ✓ |
| `survey.csv` | `835A98FCC0779B51` | `835A98FCC0779B51` | `835A98FCC0779B51` | 276193 | ✓ |

取证方式（与 fix round 2 同，控制者已在 `progress.md:793` 认可这个偏离）：临时脚本直接调 `build_dataset(SeedConfig())` + `write_csv(...)`，输出到 `%TEMP%\pe_hash_*`，**两次独立进程**（`argv[1]=A` / `B`）。**不走 CLI**——`main()` 是无条件既写盘又入库的，走它会造出 `backend/pe.db`（Ruling 68）。两次运行后各自打印 `pe.db exists in cwd = False`、`temp dir removed = True`。

> 这三个哈希同时是 H5/H6 那几条关切的**关键前提**：数据字节与复审时逐字相同，所以「复审的窗口计数与我实测不符」不可能是数据变了造成的（见关切 ②）。

---

### H2. Minor-1：AST 随机源守卫补 `np.random.*` 旧式全局采样函数

#### H2.1 改法（`backend/tests/seed/test_generate.py`）

1. **新增独立集合 `RNG_GLOBAL_FUNCS`**（19 个名字：`rand` `randn` `random` `random_sample` `ranf` `sample` `normal` `standard_normal` `uniform` `standard_uniform` `randint` `integers` `choice` `shuffle` `permutation` `binomial` `poisson` `get_state` `set_state`），**没有混进 `RNG_SOURCES`**：前者是「**用** numpy 的全局源」，后者是「**造**一个源」，混在一起会让违规消息失去指向性。`default_rng` 有意不在其中（它是全项目唯一合法入口）。
2. **新增 `_is_numpy_random_module(module)`**：判 `numpy.random` 及其子模块。
3. **新增 `_is_global_rng_call(text, imported)`**：**带接收者**的匹配，只有两种形状算违规——① `np.random.<fn>` / `numpy.random.<fn>`（末段名的前一段是 `random`、再前一段是 `np`/`numpy`）；② 裸 `<fn>` **且**该名字确实由本模块的 `from numpy.random import <fn>` 导入。`rng.normal(...)` / `self._rng.uniform(...)` 两种都不满足 → 放行。这条区分写进了该函数的 docstring。
4. **`_offenders_in` 补 `ImportFrom` 分支**：核实结果是**现有代码对 `from numpy.random import …` 完全没有分支**（原判据是 `(node.module or "").split(".")[0] == "random"`，对 `numpy.random` 得到 `"numpy"` → 不匹配）。已补：`from numpy.random import <采样函数>` 在 **import 那一行**就报，而 `from numpy.random import Generator`（只作类型标注）仍合法放行。
5. **主循环改为先预扫导入表**：`ast.walk` 是广度优先、不保证源码顺序，而裸调用必须靠导入表才能与 `rng.<fn>` 区分，故先收集 `imported_global_funcs` 再走主循环。

#### H2.2 双向取证（一）：新增禁用写法**逐条被抓**

`FORBIDDEN_WRITINGS` 从 20 条增到 **42 条**（新增 22 条）。探针逐条把源码写进 `tmp_path` 下的假模块、调 `_scan`，输出如下（**22/22 CAUGHT，既有 20 条仍 20/20 CAUGHT**）：

```
[20] CAUGHT  x = np.random.rand(10)                -> ['fake_module.py:2:np.random.rand']
[21] CAUGHT  x = np.random.randn(10)               -> ['fake_module.py:2:np.random.randn']
[22] CAUGHT  x = np.random.random(10)              -> ['fake_module.py:2:np.random.random']
[23] CAUGHT  x = np.random.random_sample(10)       -> ['fake_module.py:2:np.random.random_sample']
[24] CAUGHT  x = np.random.ranf(10)                -> ['fake_module.py:2:np.random.ranf']
[25] CAUGHT  x = np.random.sample(10)              -> ['fake_module.py:2:np.random.sample']
[26] CAUGHT  x = np.random.normal(0.0, 1.0, 10)    -> ['fake_module.py:2:np.random.normal']
[27] CAUGHT  x = np.random.standard_normal(10)     -> ['fake_module.py:2:np.random.standard_normal']
[28] CAUGHT  x = np.random.standard_uniform(10)    -> ['fake_module.py:2:np.random.standard_uniform']
[29] CAUGHT  x = np.random.uniform(0.0, 1.0, 10)   -> ['fake_module.py:2:np.random.uniform']
[30] CAUGHT  x = np.random.randint(0, 5, 10)       -> ['fake_module.py:2:np.random.randint']
[31] CAUGHT  x = np.random.integers(0, 5, 10)      -> ['fake_module.py:2:np.random.integers']
[32] CAUGHT  x = np.random.choice([1, 2, 3])       -> ['fake_module.py:2:np.random.choice']
[33] CAUGHT  np.random.shuffle(xs)                 -> ['fake_module.py:3:np.random.shuffle']
[34] CAUGHT  x = np.random.permutation(10)         -> ['fake_module.py:2:np.random.permutation']
[35] CAUGHT  x = np.random.binomial(10, 0.5, 4)    -> ['fake_module.py:2:np.random.binomial']
[36] CAUGHT  x = np.random.poisson(1.5, 4)         -> ['fake_module.py:2:np.random.poisson']
[37] CAUGHT  state = np.random.get_state()         -> ['fake_module.py:2:np.random.get_state']
[38] CAUGHT  np.random.set_state(state)            -> ['fake_module.py:2:np.random.set_state']
[39] CAUGHT  x = numpy.random.normal(0.0, 1.0, 10) -> ['fake_module.py:2:numpy.random.normal']
[40] CAUGHT  x = normal(0.0, 1.0, 10)              -> ['fake_module.py:from numpy.random import normal',
                                                        'fake_module.py:2:normal']
[41] CAUGHT  from numpy.random import normal, uniform
                                            -> ['fake_module.py:from numpy.random import normal',
                                               'fake_module.py:from numpy.random import uniform']
(既有 00-19 共 20 条：CAUGHT 20/20)
```

复审 Minor-1 那张表里 7 条 MISSED 的写法（`rand` / `randn` / `normal` / `integers` / `uniform` / `permutation` / `set_state(get_state())`）现在**全部 CAUGHT**。`[40]` 一条同时钉住「import 那一行」与「裸调用点」两处（token 写作 `2:normal`，用行号把调用点与 import 行区分开，否则只报 import 不报调用点的守卫会让这条用例假绿）。

#### H2.3 双向取证（二）：`app/seed` 现有合法 `rng.*` 调用**零违规**

```
_scan(app/seed) = []
```

新增测试 `test_the_global_rng_guard_allows_every_receiver_scoped_call_in_app_seed` 的样本**从 `app/seed` 现挖**（AST 遍历六个模块，取 `node.func.attr ∈ RNG_GLOBAL_FUNCS` 的调用点，`ast.unparse` 去重），共 **32 个不同的合法调用点**，全部写进一个假模块后 `_scan` 返回 `[]`：

```
rng.choice(AGES, size=total, p=AGE_PROBABILITIES)        rng.normal(0.0, ITEM_NOISE_SD)
rng.integers(-bound, bound + 1, size=count)              rng.normal(0.0, SEMESTER_NOISE_SD)
rng.integers(0, floor_raw)                               rng.normal(0.0, SMI_PERSON_SD, total)
rng.integers(0, hi - lo + 1)                             rng.normal(0.0, WEIGHT_NOISE_SD)
rng.integers(0, len(DEPARTMENTS), total)                 rng.normal(0.0, float(fat_sd[index]))
rng.integers(0, len(GIVEN_NAMES_FEMALE), total)          rng.normal(0.0, float(smi_sd[index]))
rng.integers(0, len(GIVEN_NAMES_MALE), total)            rng.normal(0.0, residual_sd, total_people)
rng.integers(0, len(SURNAMES), total)                    rng.normal(0.0, sd, total)
rng.integers(int(profile.swing[0]), …, size=len(ranked)) rng.normal(BMI_MEAN['female'], BMI_SD['female'], total)
rng.normal(0.0, BASE_SCORE_NOISE_SD)                     rng.normal(BMI_MEAN['male'], BMI_SD['male'], total)
rng.normal(0.0, BODY_FAT_PERSON_SD, total)               rng.normal(HEIGHT_MEAN['female'], HEIGHT_SD['female'], total)
rng.normal(0.0, HEIGHT_NOISE_SD)                         rng.normal(HEIGHT_MEAN['male'], HEIGHT_SD['male'], total)
rng.normal(cfg.latent_mean, cfg.latent_sd, total)        rng.normal(mean, sd)
rng.permutation(len(pool))                               rng.permutation(len(population))
rng.random()      rng.random(total)      rng.shuffle(sexes)      rng.uniform(*window)
```

测试里另有四条 `assert any(call.startswith("rng.normal(") …)` 之类的断言，钉住简报点名的四种合法用法（`normal` / `uniform` / `permutation` / `integers`）**确实在样本里**——否则这条负对照会空转全绿。

#### H2.4 TDD 红 → 绿

先加测试、后改实现：**RED = `24 failed, 46 passed`**（22 条新参数化用例全部 `MISSED`、负对照 `NameError: RNG_GLOBAL_FUNCS is not defined`、`_cell` 那条 `assert np.float32(1.5) == '1.5'`）→ 实现后 **GREEN = `70 passed`**。

---

### H3. Minor-2：`_cell` 补 `np.floating`

#### H3.1 改法（`backend/app/seed/generate.py`）

**唯一一行代码改动**：`if isinstance(value, float):` → `if isinstance(value, (float, np.floating)):`。进分支后先做有限性检查再 `repr(float(value))`；`np.integer` 分支保持不变。异常消息保留 `{value!r}`，因此 numpy 标量会连 dtype 一起报出来（`np.float32(nan)` 比 `nan` 更好定位），而纯 Python `float` 的消息**一字未变**（既有行为无回归）。

docstring 补了简报要求的那个 numpy 事实：**「numpy 的浮点标量里只有 `np.float64` 是 Python `float` 的子类」**，以及为什么写 `isinstance(value, float)` 会**一次绕过两件事**（`repr` 转换 + `math.isfinite`），并把「尚未触发 ≠ 不可达」写明。

#### H3.2 单元级取证（逐个 dtype 实调 `_cell`）

```
float16    1.5    -> '1.5'          float32   nan  -> ValueError: …非有限浮点值 np.float32(nan)…
float32    1.5    -> '1.5'          float16   nan  -> ValueError: …非有限浮点值 np.float16(nan)…
float64    1.5    -> '1.5'          float64   nan  -> ValueError: …非有限浮点值 np.float64(nan)…
longdouble 1.5    -> '1.5'          longdouble nan -> ValueError: …非有限浮点值 np.longdouble('nan')…
float32   -0.25   -> '-0.25'        float32   inf  -> ValueError: …非有限浮点值 np.float32(inf)…
int64/int32/uint8 3 -> 3            float32  -inf  -> ValueError: …非有限浮点值 np.float32(-inf)…
None -> ''    7 -> 7    2.5 -> '2.5'    'abc' -> 'abc'      float64  inf -> ValueError
dict + nan -> ValueError: Out of range float values are not JSON compliant   ← allow_nan=False 仍在
对照：repr(np.float32(1.5)) == 'np.float32(1.5)'  ← 这就是改前会原样落进 CSV 的字符串
```

复审 Minor-2 那张表里三行「绕过守卫」（`np.float32(nan)` → `nan`、`np.float32(inf)` → `inf`、`np.float32(1.5)` → repr 泄漏）现在**全部被拦下**。

#### H3.3 **CSV 文本级**取证（简报点名的手法：走完整 `write_csv`，不只调一次 `_cell`）

把 `fitness` 的全部测量列换成 `np.float32`（`strength_count` 换 `np.int64`），走 `inject_dirty` → `write_csv` → 读回文本：

```
被换成 np.float32 的 height_cm 单元格 = 237/243（其余 6 个是 build_dataset 已注入的 missing → None，被跳过）
落盘字节 = 31462   行数 = 249
grep 'np.float32('  -> 0 次命中        grep 'nan' -> 0 次命中
grep 'np.float64('  -> 0 次命中        grep 'inf' -> 0 次命中
grep 'np.int64('    -> 0 次命中
样例行: 2022110001,2024-2025|week1,2024-09-02,166.0,64.30000305175781,2546.0,8.800000190734863,…
nan 落盘（把 height_cm 换成 np.float32('nan') 再 write_csv）-> ValueError: …非有限浮点值 np.float32(nan)…
```

样例行里的 `64.30000305175781` 是 float32→float64 的正常展宽（**不是** dtype repr 泄漏），适配器 `float()` 能直接解析。最后两行证明守卫是在**落盘路径上**生效的，不是只在直接调 `_cell` 时生效。

（附：改前用同一手法实测过 `nan` / `inf` 在三个 CSV 的**合法**产物里都是 0 次命中，所以「文本里 grep 不到 `nan`」这个断言不会被正常数据误触发。）

---

### H4. Minor-4：四条响亮失败守卫的自证测试

#### H4.1 四条守卫的触发条件、异常类型、消息全文

全部用**合成输入**直接打到抛出的那一行（`_synthetic_info(...)` 造 `info`、手工造 `deltas` / `bundle`），不靠调 `SeedConfig` 去撞。行号是**本轮加注释之后**的（原 `:606/:618/:805/:813` → 现 `:651/:663/:850/:858`）。

| # | 位置 | 异常 | 触发条件（合成输入） | 消息全文 |
|---|---|---|---|---|
| 1 | `fitness.py:850`（原 `:805`） | `RuntimeError` | `label="稳步提升"`、`curr` 六项全 **10**（表底）、`deltas` 全 0 → `prev` 已是最低档，`_correction_move` 需要 `direction=-1` 却一项都推不动 → 返回 `None` | `趋势校正推不动了：student_id=9001 标签「稳步提升」，第 0 轮后 Delta'=0、delta_i'={…六项全 0…}、被判成「稳定」，而六项已全部到达表内端点档。说明可行域筛选放进了一个装不下该标签的学生。` |
| 2 | 同上 | `RuntimeError` | `label="持续下滑"`、`curr` 六项全 **100**（表顶）、`deltas` 全 0 → 需要 `direction=+1` 却一项都推不动 | `趋势校正推不动了：student_id=9001 标签「持续下滑」，第 0 轮后 Delta'=0、delta_i'={…六项全 0…}、被判成「稳定」，而六项已全部到达表内端点档。说明可行域筛选放进了一个装不下该标签的学生。` |
| 3 | `fitness.py:858`（原 `:813`） | `RuntimeError` | `label="波动大"`、`curr` 六项全 100、`deltas` = 三正三负各 ±12 → 负号三项的 `prev_target=112` 被 clip 回 100 → `delta_i'=0`（两边都不计入）→ 永远只有 3 正 0 负；而波动大分支推的是**幅值最大的正号项**、方向 `-1`，每轮把判据推得更远 → 跑满 8 轮 | `趋势校正 8 轮仍未达判据：student_id=9004 标签「波动大」，Delta'=22、delta_i'={vital_capacity: 15, sprint_50m: 90, sit_and_reach: 15, standing_jump: 0, pull_up_or_sit_up: 0, distance_run: 0}、被判成「稳步提升」。不静默放行标签与数据不符的学生。` |
| 4 | `fitness.py:651`（原 `:606`） | `ValueError` | 4 人、`trend_mix` 给「持续下滑」配额 2，而合成 `bundle` 里只有 1 人的持续下滑窗口非 `None` | `趋势标签「持续下滑」的可行池不足：需要 2 人，实有 1 人（全体 4 人）。判据见 _delta_target_windows 的注释；不得静默改标签，因为 trend_label 是 Task 8 交叉验证与规则 Y4 的真值。` |
| 5 | `fitness.py:663`（原 `:618`） | `ValueError` | 4 人、「持续下滑」配额 1（给了 sid 1），sid 4 的四类窗口**全 `None`** → 余下 3 人里带着一个构造不出来的稳定标签 | `余下 3 人应全部标为「稳定」（配额 3），但其中 1 人在该类可行域之外（例如 student_id [4]）。前三类挑选时已优先让出稳定不可行的人，仍然不够，说明可行域筛选或配额本身与该人群的得分分布不相容；不得静默改标签。` |
| 6 | 同 #4，走**真实路径** | `ValueError` | `SeedConfig(students=120, trend_mix={"持续下滑":0.9,"波动大":0.0,"稳步提升":0.0,"稳定":0.1})` → `build_dataset(cfg)` 整体抛，而不是静默少生成 | `趋势标签「持续下滑」的可行池不足：需要 108 人，实有 54 人（全体 120 人）。判据见 …；不得静默改标签，…` |

**消息里「关键数字」的核实结论（简报要求「没有就补上」）：四条全都已经有了，本轮一字未改。**
- `:651`（原 `:606`）：`需要 2 人，实有 1 人（全体 4 人）` → **需要数与实有数齐备** ✓（Ruling 65）
- `:663`（原 `:618`）：`余下 3 人 …（配额 3）… 其中 1 人在该类可行域之外（例如 student_id [4]）` → 需要数（配额 3）、实有数（余下 3 人 / 其中 1 人不可行）、以及**是哪几个 `student_id`** 齐备 ✓。它没有逐字写「实有可行 2 人」，但 `3 − 1` 一步可得；我判定满足 Ruling 65 故**未改消息**，若控制者认为必须逐字给出，见关切 ⑤。
- `:850`（原 `:805`）：`student_id=9001` + `第 0 轮后` + `Delta'=0` + `被判成「稳定」` → **学生标识与迭代轮数齐备** ✓
- `:858`（原 `:813`）：`student_id=9004` + `趋势校正 8 轮仍未达判据`（`CORRECTION_MAX_ROUNDS`）+ `Delta'=22` + `被判成「稳步提升」` → **齐备** ✓

#### H4.2 断言强度：不靠行号，靠消息的**区分性**前缀

四条测试各自断言异常类型 + 消息里的关键数字 + 一句**只属于这一条守卫**的前缀（`趋势校正推不动了` / `轮仍未达判据` / `可行池不足` / `余下 N 人应全部标为「稳定」`）。这样两条 `RuntimeError` 之间、两条 `ValueError` 之间不会互相顶替——只断言类型的话，守卫被换成另一条也照样绿。docstring 里**有意不写 `fitness.py` 的行号**：本轮加一段注释就让四个行号全部偏移了 45 行，写进去当场过期。

#### H4.3 **变异测试**：证明这 6 条不是空转

把四处守卫按复审 Minor-4 描述的方式**静默化**（`raise` → `return prev_targets, rounds`、`if len(pool) < need` → `if len(pool) < -1`、`if infeasible` → `if infeasible and False`），然后跑这 6 条：

```
FAILED …no_item_can_be_moved_any_further[表底-稳步提升]   - Failed: DID NOT RAISE RuntimeError
FAILED …no_item_can_be_moved_any_further[表顶-持续下滑]   - Failed: DID NOT RAISE RuntimeError
FAILED …the_round_cap_is_exhausted                        - Failed: DID NOT RAISE RuntimeError
FAILED …when_a_feasible_pool_is_short                     - Failed: DID NOT RAISE ValueError
FAILED …residual_holds_a_stable_infeasible_student        - Failed: DID NOT RAISE ValueError
FAILED …instead_of_silently_generating_fewer_students     - TypeError: Generator.uniform() argument after * must be an iterable, not NoneType
6 failed, 15 deselected in 0.58s
```

**5/6 是干净的 `DID NOT RAISE`**，正是复审担心的「静默放行」场景；第 6 条（真实路径）红成下游 `TypeError`，因为同时静默化两条 `_trend_labels` 守卫后，会有一个 `windows[label] is None` 的学生被塞进 `_initial_deltas` → `rng.uniform(*None)`。这条附带说明：**在真实流水线上静默化池守卫不会产出「自洽地错」的数据，而是会在两步之后炸开**——复审设想的 `pool[:need]` + 余下改标签那种改法才会自洽地错，而那种改法现在会被 #4/#5/#6 三条一起拦住。变异全部**已还原**，`Select-String "MUTATION-TEST-TEMPORARY"` 复核为空，还原后 310 passed（H0）。

---

### H5. Minor-7：零宽窗口——**我自己算的那笔账**，结论是「不安全」

#### H5.1 结论

简报 §2.4 那条 ⚠️ 让我自己算「`Delta_target` 被钳成单点 + 校正预留为 0」在「`稳定` 判据是 `|Delta| < 5` 开区间、量化噪声最多 ±7.65 分」下是否安全。

**算下来：不安全。所以我没有写「可以接受」，而是按简报的指示在注释里如实写明这是一颗已知的未爆哑弹，并在此上报（关切 ④）。**

具体地：**简报给的那条论证路线（「单点目标落在区间中央，所以量化噪声推不出 ±5」）是错的**——量化确实能把它推出 `+5`。真正兜住它的不是窗口，是校正循环。

#### H5.2 那笔账

**第一步：零宽时 `Delta_target` 到底是哪个单点。** 零宽意味着 `magnitude = 0`，于是 `lo = max(low, b − 0)`、`hi = min(high, b + 0)`，非 `None` 就要求 `b` 同时落进名义区间与纯度下界里。对「稳定」，名义区间是 `(−2, +2)`，故**零宽必有 `|b| ≤ 2`**。而 `b = 15 × bmi_delta / 100`、BMI 得分档位只有 `{60, 80, 100}` → `bmi_delta ∈ {−40,−20,0,20,40}` → `b ∈ {−6,−3,0,+3,+6}`，其中只有 **`b = 0`** 满足 `|b| ≤ 2`。实测证实：145 个零宽学生的窗口**一律是 `(0.0, 0.0)`**、`bmi_delta` **一律是 0**。所以 `Delta_target ≡ 0`、`base = 100(0−0)/85 = 0`、`rounded = 0`，`delta_i` 只剩 `[−2,+2]` 的**零和**整数抖动。单点确实落在 `±5` 开区间的正中央——简报到这里是对的。

**第二步：量化能不能把它推出去。** 落档是**单向**的（`prev_i ≤ prev_target_i` ⟹ `delta_i' ≥ delta_i`）。逐项看（`prev_target_i = curr_i − jitter_i`，`curr_i` 本身是官方档）：
- `jitter_i ≤ 0` → `prev_target ≥ curr` → 就低取档回到 `curr`（或更高的官方档）→ `delta_i' ∈ [−2, 0]`；要拿到负值必须 `curr_i + |jitter_i|` **恰好**是官方档，只有 62–78 那段 2 分细档满足，故 `|delta_i'| ≤ 2`。
- `jitter_i > 0` → `prev_target` 落到 `curr_i` 下面那一档 → `delta_i' = 该处的档距`，即 `{2, 5, 10}`（60 分以下是 **10**）。

零和 + 界 2 的组合里最多能有 **4 个正号项**（`(+1,+1,+1,+1,−2,−2)`；5 个正号项要 `−5` 来平衡，超出界 2）。于是上界是

```
Σ w_i·delta_i' ≤ (20 + 20 + 15 + 10) × 10 = 650   →   Delta' 最高约 +6.5
```

**`+6.5 > +5`，越过开区间上边界。** 所以「单点在中央」这个论证不成立：抖动虽然零和，但**权重不是均匀的**（六项是 `15/20/10/10/10/20`），零和抖动经加权后不再是 0；再叠上单向落档，净效果是**系统性上抬**。

下边界则是**结构性**安全的：`Σ w_i·delta_i' ≥ −(20+20+15+10)×2 = −130` → `Delta' ≥ 约 −1.3`，离 `−5` 还有 3.7 分。**风险是单边的：只有 `+5` 会被顶穿。**

（顺带核出简报口径的一处偏差：`±7.65 分` 是 `85 × 9 / 100` 那个**通用**上界（每项最多吃 9 分）；在「零宽 + 界 2 抖动」这个特定条件下，真实上界是 **6.5**，因为 `delta_i'` 只能取档距 `{2,5,10}`、且最多 4 项为正。见关切 ⑥。）

**第三步：穷举实测。** 对生产配置里那 **91 个**真正被标为「稳定」且零宽的学生，穷举**全部 1751 个**和为 0 的 `[−2,+2]^6` 抖动向量（6 项全自由，故 91 × 1751 = **159341 组**），逐组跑真实的 `_settle_prev_targets`：

```
round-0（校正前）的 Delta' 取值范围 = [−1, +6]        ← 上界与手算的 +6.5 同向
出 (−5, +5) 带的 = 110 / 159341（0.069%），**全部在 +5 一侧**
需要校正的 = 117 / 159341        max_rounds = 2        RuntimeError = 0
最坏例子: sid=448  curr = {vital 40, sprint 50, sit_and_reach 50, standing_jump 85, pull_up 90, distance_run 50}
          jitter = {+1, +1, −2, −2, +1, +1}  →  round-0 Delta' = +6，1 轮校正后回到带内
          手算复核: 15×10 + 20×10 + 10×0 + 10×0 + 10×5 + 20×10 = 600 → 600/100 = 6 ✓
```

**第四步：为什么校正循环兜得住（这才是真正的安全论证）。** 出带只朝一个方向（`Delta'` 偏高），故 `_correction_move` 只需要 `direction = +1`（把 `prev` 往上推）；而顶穿上界的那几项**恰恰是低分项**（`delta_i' = 10` 意味着 `curr_i ∈ {20..60}`），它们的 `prev_i < 100` 恒成立 → **永远推得动**。反过来，`move is None`（即 `:850`）要求六项全部 `prev_i = 100`，那只有在 `curr` 全 100 且 `jitter` 全 0 时才可能，而那时 `Delta' = 0` 本来就达标、根本不进校正。每轮移动 ≥1 分（`w=20` 且非端点档时 2 分），把 `+6.5` 拉回带内最多 3 轮，上限是 `CORRECTION_MAX_ROUNDS = 8` → **2.7× 余量**，与实测 `max_rounds = 2` 一致。

**第五步：生产那一轮的实际发生数。** 91 个零宽学生里**一个都没触发校正**（`rounds > 0` 计数为 0）；全 500 人 `triggered = 16`、`max_rounds = 1`、`RuntimeError = 0`，触发者按标签是 `{持续下滑: 7, 稳定: 9}`，而那 9 个「稳定」**全部来自非零宽窗口**。每次抽样的出带概率约 `110/1751 ≈ 6.3%`（按人算，取决于其 `curr` 的档距结构；对全部 91 人平均是 `110/159341 ≈ 0.069%`），故一轮 500 人里期望值 < 0.1 人——「实测 0 次」是期望之内的，**不是「不可能发生」的证据**。

**结论**：这颗哑弹**当前不炸，但不是因为窗口留了余量（余量是 0），而是因为校正循环在唯一会被顶穿的那一侧永远推得动**。安全性从「筛选时预留」整体转移到了「运行时兜底」，而运行时的兜底就是 `:850`/`:858` 那两条 `RuntimeError`——本轮 H4 刚给它们补上自证测试，正好把这层依赖钉住了。**Task 9 一旦调大 `jitter`、调小 `CORRECTION_STEP`/`CORRECTION_RESERVE`、或换一张档距更大的评分表，上面第二步的 650 与第四步的 3 轮都会变，这笔账必须重算。**

#### H5.3 实测口径（与复审不一致，见关切 ②）

`SeedConfig()` 缺省 500 人 / `seed=20250828`，直接读 `_trend_inputs` 产出的 bundle：

| 标签 | 全量可行 | 零宽 | 最小窗宽 | 中位窗宽 | 复审报的 |
|---|---|---|---|---|---|
| 波动大 | **257** | 257（设计如此，不设 Delta 目标） | 0.0 | 0.0 | 260 |
| 持续下滑 | **215** | 0 | **0.75** | 6.75 | 203 / min 1.650 |
| 稳步提升 | **486** | 0 | 5.45 | 12.0 | 487 / 5.450 / 12.000 |
| 稳定 | **493** | **145** | 0.0 | 4.0 | 489 / **133** |

贪心分配后的**池大小**（用真实标签重建，`波动大` 先挑）：`波动大 257 / 持续下滑 161 / 稳步提升 321`（复审：260 / 152 / 318；报告 G5：260 / 150 / 322）。`room − jitter − CORRECTION_RESERVE ≤ 0` 的人数：**152**（复审：144）。

#### H5.4 据此写下的注释原文（`backend/app/seed/fitness.py`，紧贴 `magnitude = …` 那一行之前）

```python
        # ⚠️ 已知的未爆哑弹（评审 Minor-7；本轮按控制者裁定**只补注释、不改公式**——改窗口
        # 会平移随机流、让全部 CSV 字节与已取证哈希作废）。这个 ``max(0.0, …)`` 钳位在
        # ``room ≤ profile.jitter + CORRECTION_RESERVE``（稳定类即 ``room ≤ 12``）时把
        # ``magnitude`` 压成 0，窗口塌成**单点** ``(b, b)``：该生的 ``Delta_target`` 不再是
        # 抽样区间而是一个确定值，且**一分校正预留都没拿到**。实测（``SeedConfig()`` 缺省
        # 500 人 / seed=20250828，直接读 ``_trend_inputs`` 产出的 bundle）：稳定类可行
        # 493 人里 **145 人**是零宽，实际被标为「稳定」的 200 人里 **91 人**是零宽；另三类
        # 一个都没有（持续下滑/稳步提升的名义区间宽 12 分，钳位后直接 ``lo > hi`` 判不可行，
        # 波动大的窗口本来就是 ``(0.0, 0.0)``，它不设 Delta 目标）。
        #
        # **单点目标本身并不安全，不要把它记成「落在 ±5 开区间中央所以没事」**：
        # 零宽必有 ``|b| ≤ 2``，而 BMI 档位只有 {60, 80, 100} → ``b ∈ {−6,−3,0,3,6}``，故
        # 这 145 人的窗口一律是 ``(0.0, 0.0)``、``bmi_delta`` 一律为 0 → ``Delta_target ≡ 0``、
        # ``base = 0``、``delta_i`` 只剩 ``[−2, +2]`` 的零和抖动。而落档是**单向**的
        # （``prev_i ≤ prev_target_i`` ⟹ ``delta_i' ≥ delta_i``），界 2 的零和抖动最多能有
        # **4 个正号项**（``(+1,+1,+1,+1,−2,−2)``），每个正号项吃掉的是它下面那一档的档距
        # （60 分以下是 10 分），故 ``Σ w_i·delta_i' ≤ (20+20+15+10)×10 = 650`` →
        # ``Delta'`` 最高约 **+6.5**，**已经越过 ``|Delta'| < 5`` 的上边界**。穷举这 91 人 ×
        # 全部 1751 个零和抖动向量（159341 组）实测：round-0 的 ``Delta'`` 落在 ``[−1, +6]``，
        # 其中 **110 组出带**（全在 ``+5`` 一侧，会被判成「稳步提升」）。
        # 下边界则是**结构性**安全的：``delta_i' < 0`` 要求 ``curr_i + |jitter|`` 恰好是官方档
        # （只有 62–78 那段 2 分细档满足），故 ``|delta_i'| ≤ 2``、
        # ``Σ w_i·delta_i' ≥ −(20+20+15+10)×2 = −130`` → ``Delta'`` 约 ≥ ``−1.3``（实测 −1），
        # 离 ``−5`` 很远。**风险因此是单边的：只有上边界会被顶穿。**
        #
        # **真正兜住它的是校正循环，不是这个窗口**：出带只朝一个方向，故
        # :func:`_correction_move` 只需要 ``direction = +1``（把 ``prev`` 往上推），而顶穿上界
        # 的那几项恰恰是低分项、``prev_i < 100`` 恒成立 → 永远推得动；每轮移动 ≥1 分
        # （w=20 且非端点档时 2 分），把 +6.5 拉回带内最多 3 轮，上限是
        # :data:`CORRECTION_MAX_ROUNDS` = 8。实测那 159341 组里 117 组需要校正、**最多 2 轮**、
        # ``RuntimeError`` **0 次**；生产那一轮 91 个零宽学生**一个都没触发校正**
        # （全 500 人 ``triggered = 16``、``max_rounds = 1``）。
        #
        # 与 :data:`CORRECTION_RESERVE` 的关系：预留的全部意义是「筛选时先扣掉一轮校正的
        # 空间」，钳位到 0 等于这批人的安全性**全部押在校正循环推得动上**，窗口一点余量都没
        # 给。所以 :func:`_settle_prev_targets` 末尾那两条 ``RuntimeError``（「趋势校正推不动
        # 了」与「N 轮仍未达判据」）是它唯一的兜底，两者的自证测试见
        # ``tests/seed/test_fitness.py``。
        # **Task 9 若调大 ``jitter``、调小 ``CORRECTION_STEP`` / ``CORRECTION_RESERVE``，或换
        # 一张档距更大的评分表，上面这笔账必须重算**：零宽人群会变大，而校正每轮的步长会
        # 变小，两个方向都在吃这 8 轮的余量。
        # （数字的口径：145/493 是**稳定类可行**的人里零宽的占比，91/200 是**实际被标为稳定**
        # 的人里的占比；复审报告写的是 133/489，本轮三条独立路径重测都是 145/493——含直接从
        # 记录的 ``score_*`` 列复算，且三个 CSV 的 SHA256 与复审时逐字相同，故数据没变。
        # 差异已作为关切上报。）
```

注释里**有意不写 `:805`/`:813` 这两个行号**：这段注释本身就让它们偏移到了 `:850`/`:858`，写进去当场过期。改为按消息前缀指认（「趋势校正推不动了」/「N 轮仍未达判据」）。

---

### H6. 关切

#### ① AST 守卫仍有两种**别名**写法漏网（简报规定的匹配规则之外，我没有自作主张扩大）

简报 §2.1 明确规定了匹配形状（`np.random.<fn>` / `numpy.random.<fn>` / 由 `from numpy.random import <fn>` 导入的裸名），并警告不要一刀切按末段名匹配（会误伤 `rng.normal(...)`）。我**严格照这条规则实现**，因此下面两种别名写法**仍然 MISSED**（探针实测）：

```
MISSED!  import numpy.random as npr ; x = npr.normal(0.0, 1.0, 10)     -> []
MISSED!  from numpy import random   ; x = random.normal(0.0, 1.0, 10)  -> []
CAUGHT   from numpy.random import normal as n ; x = n(0.0, 1.0, 10)    -> [import 那一行]（调用点本身不报）
CAUGHT   x = np.random.default_rng(0).normal(0.0, 1.0, 10)             -> [default_rng]（本来就该报）
```

- **后果**：与复审 Minor-1 同级——「隐藏第二随机源」还剩两个侧门。今天 `app/seed` 里没有这两种写法（`_scan(app/seed) == []`），是**潜在**缺口。
- **为什么我没顺手补**：把它们堵住的最省事写法是「凡是 `<receiver>.<fn>` 且 `<fn> ∈ RNG_GLOBAL_FUNCS` 且 `<receiver>` 末段叫 `random` 就报」，而那会**误伤**一个恰好叫 `random` 的合法局部变量（`random = np.random.default_rng(0)` 之后 `random.normal(...)` 是完全合法的）——正是简报警告的那类误伤。要无误伤地堵住，得在预扫阶段解析 `import numpy.random as X` / `from numpy import random as X` 的**别名表**（约 6–10 行），这属于简报未要求的设计变更，故上报而不自行决定。
- **建议**：授权我在下一轮加一张「numpy 全局随机模块别名表」到那个已有的预扫阶段（`imported_global_funcs` 旁边），即可无误伤地堵住这两种写法。

#### ② 复审的**窗口 / 池 / 校正计数**在字节完全相同的数据上不可复现（三条独立路径都指向我的数字）

复审 Minor-7 与「报告数字复核表」给的 `133/489`、`260/203/487/489`、`152/318`、`room≤12 = 144`，以及报告 G4 / 复审都给的 `triggered = 19 / {0:481, 1:19}`，**我一个都复现不出来**。我在 HEAD（`945877f`，代码与复审所看的 `bed07ed` 在 `backend/` 下**逐字相同**：`git diff --stat bed07ed..1fbc35f -- backend` 输出为空）上实测：

| 量 | 报告 / 复审 | 我实测 | 我的三条独立路径 |
|---|---|---|---|
| 稳定类可行 / 其中零宽 | 489 / **133** | **493 / 145** | ① 直接读 `_trend_inputs` 的 bundle；② 用记录的 `score_*` 列重算 `magnitude`（得 152 人 `magnitude==0`，与 ① 逐字相同）；③ 直接调 `_delta_target_windows` |
| 波动大 全量可行 | 260 | **257** | 直接从记录 `score_*` 列按字面判据数（`free==6 且 min≥16 且 max≤84`） |
| 持续下滑 / 稳步提升 全量可行 | 203 / 487 | **215 / 486** | 同 ① |
| 池大小（贪心分配后） | 260 / **152** / **318** | **257 / 161 / 321** | 用**真实标签**重建每一轮的 `pool`（不重放 rng） |
| `room−jitter−reserve ≤ 0` 人数 | 144 | **152** | 同 ①② |
| 校正循环 `triggered` / 轮数直方图 | **19** / `{0:481, 1:19}` | **16** / `{0:484, 1:16}` | 用既有测试 `test_trend_correction_loop_…` 自己的 monkeypatch 路径读 `stats`；零注入配置下同为 16 |

**关键前提**：三个 CSV 的 SHA256 与字节数（244496 / 107745 / 276193）与复审时**逐字相同**（H1），且 `_trend_inputs` 的 `curr` 与记录的本学年 week1 `score_*` 列**3000/3000 完全一致**（0 处不符）。所以数据没变、`curr` 的口径也没有歧义，差异只能来自复审那一侧的测量方法（我无从复核它用的 `bmi_delta` 与 `free` 是从哪里取的；`持续下滑` 的窗宽对 `b` 最敏感，而它的计数恰好差得最多（203 vs 215）、最小窗宽也对不上（1.650 vs 0.75），这条线索指向 `bmi_delta` 的取法）。

- **后果**：`progress.md:841` 那条「**可行池 `150 / 322` → `152 / 318`**」的更正，把报告数字改成了另一组同样不可复现的数字，并且写在了标着「控制者逐条核实」的段落里（正是硬规矩 #5 要防的形态）。而 `triggered = 19` 被报告 G4 与复审**双双**写成 19，两处都不可复现。
- **我没有改任何文档**（不是我的交付物），只在本报告里给出实测值与取法。请控制者裁定：以哪一组为准，以及是否需要向复审追问它的 `bmi_delta` 取法。
- **置信度：高**（三条独立路径互证 + CSV 字节逐字相同 + `curr` 与 `score_*` 3000/3000 一致）。

#### ③ 我写进源码注释的数字用的是**我自己的实测值**，不是简报给的 `133/489`

简报 §2.4 第 1 点要求注释写「实测 500 人配置下有 133/489 名「稳定」池学生落入」。我**没有照抄**，写的是 `145/493`（可行口径）与 `91/200`（实际被标为稳定的口径），并在注释末尾用三行注明了两个口径的差别、复审的数字、以及「三个 CSV 的 SHA256 与复审时逐字相同，故数据没变」。理由：把我自己复现不出来的数字写进源码，等于给一个未验证的数盖章（硬规矩 #5）。若控制者裁定以复审的 133/489 为准，这三行注释与 H5.3 的表需要同步改回。

#### ④ **裁定请求**：零宽窗口按我的账是「不安全」，请裁定处置

按简报 §2.4 的 ⚠️ 指示，我算下来的结论是**不安全**（`Delta'` 可达 `+6.5`，越过 `+5`；穷举 159341 组里 110 组真的出带），因此我**没有写「可以接受」**，注释里写的是「已知的未爆哑弹 + 真正的兜底是校正循环 + Task 9 改这三个参数时必须重算」。请控制者裁定以下之一：

- **(a) 接受现状**（我的建议）：注释已把「安全性来自校正循环而不是窗口」写明，且本轮 H4 刚给那两条 `RuntimeError` 补了自证测试与变异测试，这层依赖现在是被钉住的。代价：`CORRECTION_RESERVE` 对 145/493 的稳定可行人群名不副实。
- **(b) 改窗口公式**（复审 Minor-7 的建议：`room − jitter − reserve < 0` → 该类判不可行 `None`）：**会让全部 CSV 字节作废**（稳定池会少 145 人，`_trend_labels` 的洗牌与配额随之全变），本轮明确不做；若要做，需与 Task 9 的调参一起排期并重做全部可复现性取证。
- **(c) 只加一条断言把退化行为钉住**（复审建议的那条：`curr` 六项全 100、`bmi_delta = 0` → `windows["稳定"] == (0.0, 0.0)` 而非 `None`）。这条**不改行为、不平移随机流**，我本轮**没有加**，因为简报 §2.4 只要求「补注释」，加测试超出授权范围。若控制者要，下一轮 5 分钟可补。

#### ⑤ `:663`（原 `:618`）的消息是否满足 Ruling 65 的「需要数与实有数」，我判定为满足、故未改，请复核

简报要求「`:606`/`:618` 必须报出需要数与实有数，没有就补上」。核实结果：`:651`（原 `:606`）逐字给出 `需要 2 人，实有 1 人`，**无争议** ✓。`:663`（原 `:618`）给的是 `余下 3 人 …（配额 3）… 其中 1 人在该类可行域之外（例如 student_id [4]）`——**需要数**（配额 3）与**实有数**（余下 3 人、其中 1 人不可行）都在，但没有逐字写出「实有可行 2 人」这个差值。我判定 `3 − 1` 一步可得、且它额外报了 `student_id` 清单（比一个数字更好定位），故**没有改消息**（改消息文本会让 H4 那 5 条断言全部要跟着改，且不属于「补上缺失的数字」）。若控制者认为必须逐字给出可行数，这是一处一行改动 + 一处断言更新。

#### ⑥ 简报 §2.4 的「量化噪声最多 ±7.65 分」在**这个条件下**不是真实上界（真实上界 6.5，且是单边的）

`±7.65` 是 `85 × 9 / 100` 那个通用上界（每项就低取档最多吃 9 分），它对「任意 `delta_i`」成立；但零宽窗口下 `delta_i` 被限死在 `[−2,+2]` 的零和抖动里，于是：正号侧每项吃的是**档距**（`{2,5,10}`，不是 9）且最多 4 项为正 → 上界 `(20+20+15+10)×10/100 = 6.5`；负号侧 `|delta_i'| ≤ 2` → 下界约 `−1.3`。**「±」这个对称记法在这里也是错的：风险完全在 `+` 一侧。** 这条不影响任何代码，只是简报的论证前提需要更正——而正因为按 `±7.65` 对称地算，才会得出「单点在中央、两边各留 5 分余量、7.65 > 5 所以危险但对称危险」这种模糊结论；按真实的单边账算，结论是明确的「上界会被顶穿、下界结构性安全、兜底方向唯一」。

#### ⑦ 变异测试顺带查出的一件事：静默化 `_trend_labels` 的池守卫在**真实流水线**上不会「自洽地错」，而是两步之后炸开

见 H4.3 第 6 条。复审 Minor-4 的「后果」段写的是「280 条测试仍会全绿——因为静默放行恰好会让当次数据自洽地错」。我实测：把 `raise ValueError` 静默化后，`_trend_labels` 会给一个 `windows[label] is None` 的学生发标签，`_initial_deltas` 立刻 `rng.uniform(*None)` → `TypeError`。所以**对这两条 `ValueError` 而言，「静默放行」这个变异在真实路径上是自曝的**（复审设想的 `pool[:need]` + 余下改标签那种改法才会自洽地错，而那种改法会被我新增的 #4/#5/#6 三条一起拦住）。这不是缺陷，只是复审那段推理的一个前提需要收窄；对两条 `RuntimeError` 而言复审的推理**完全成立**（静默化后数据确实自洽地错，5/6 那五条 `DID NOT RAISE` 就是证据）。

---

### H7. 前向约束

**无新增，沿用 fix round 2 的清单**（`progress.md:804-809` 与本报告 G12）。本轮**没有**改任何生成逻辑、没有加/删任何随机数消耗点、没有动 `write_csv` 的三文件契约、`make_batch_key`、日期零填充，也没有加 `students.csv`，故 G12 第 4 条那份「随机流形状参数清单（六个）」与第 9/10 条一字不变。

只有一条**加强**（不是新增）：G12 第 4 条列的六个形状参数之外，本轮把「AST 随机源守卫」的覆盖面扩到了 numpy 旧式全局采样函数，因此 **Task 9 调参时若顺手写 `np.random.normal(...)` 会当场红**（以前不会）。这是守卫变严，不是约束变多。若控制者采纳关切 ① 的建议补上别名表，Task 9 的派单里应提一句「随机数只能用传进来的 `rng`」。

---

### H8. 本轮 git 输出

```
$ git log --oneline -1
945877f fix: AST 守卫补 numpy 全局随机源，_cell 补 np.floating，四条响亮失败守卫补自证测试

$ git status --short
（无输出：工作树干净。backend/pe.db 全程未创建（Ruling 68，每次取证后 Test-Path 复核 False）；
  backend/data/seed/ 全程保持空目录（0 个文件，在 .gitignore:20 内）；
  .superpowers/ 在 .gitignore:10 内，本报告与账本本来就不进版本库。）

$ git show --stat --oneline HEAD
 backend/app/seed/fitness.py         |  45 +++++++      ← 全是注释（过滤注释行后 diff 为空）
 backend/app/seed/generate.py        |  13 +-           ← 代码只有 1 行：(float, np.floating)
 backend/tests/seed/test_fitness.py  | 193 +++++++++++++++++++++++++++
 backend/tests/seed/test_generate.py | 255 +++++++++++++++++++++++++++++++++++-
 4 files changed, 499 insertions(+), 7 deletions(-)
```

临时探针文件（`%TEMP%\pe_probe\probe1.py` … `probe12.py`，共 12 个）与全部临时 CSV 目录（`%TEMP%\pe_hash_*` / `pe_csv_*` / `pe_f32_*` / `pe_guard_*`）**已全部删除**，`Test-Path` 与 `Get-ChildItem -Filter` 逐一复核为空/`False`。

---

## Fix Round 4

基线 `945877f` → 本轮 commit **`dd07ae4`**（**一个** commit）。范围严格照简报 §2 的三件事：§2.1 更正源码注释里那组被驳回的错测数字、§2.2 AST 守卫补 import 别名表、§2.3 加一条钉住零宽窗口退化行为的断言。§3「明确不要做的事」逐条遵守：窗口公式未改、三条结论一字未撤、`_correction_move` 的 3 条 0 命中分支未碰、m4 容差未收紧、`app/domain/indicators.py` 未动、Task 8 的 `classify_trend` / `national_total` / `derive` 未实现、未做二分法调参、未做任何简报外的重构。

### I0. 结论速览

| 项 | 值 |
|---|---|
| 测试数 | **310 → 318**（+8） |
| `pytest -q`（在 `backend/` 下） | **318 passed in 10.06s** |
| `pytest -q -W error` | **318 passed in 9.96s**，**洁净**（输出里没有 warnings 段） |
| 既有 310 条的断言 | **一条未改、未放宽**（见 I0.1） |
| 三个 CSV 的 SHA256 前 16 | **逐字未变**（见 I1） |
| 生成逻辑改动 | **0 行**（`fitness.py` 的 diff 过滤注释行后为空，见 I0.2） |
| `backend/pe.db` | 全程未创建（每次取证后 `Test-Path` 复核为 `False`） |
| `backend/data/seed/` | 全程保持**空目录**（0 个文件）；取证一律写 `%TEMP%` |
| 新增测试的分布 | `test_generate.py` 70 → **77**（+7）；`test_fitness.py` 21 → **22**（+1）；`test_trend_oracle.py` 14 → 14 |
| `MUTATION-TEST-TEMPORARY` 残留 | **0**（见 I5） |

+8 的构成：6 条 AST 守卫参数化用例（三种 import 别名写法各两条，`FORBIDDEN_WRITINGS` 42 → **48**）+ 1 条 AST 负对照（`test_the_guard_allows_a_local_variable_that_happens_to_be_named_random`，内含两个形状）+ 1 条 §2.3 断言（`test_zero_room_collapses_the_stable_window_to_a_single_point`）。

#### I0.1 「既有断言一条未改」的取证

`git diff --unified=0 -- backend/tests/` 里**全部 26 行删除**如下，没有一行含 `assert`：

```
-    ``np.random.<采样函数>`` 旧式全局采样写法（:data:`RNG_GLOBAL_FUNCS`）都算违规。        ← 守卫测试的 docstring（扩写）
-    **判据本身由下面三条测试双向钉住**：…                                                  ← 同上（三条 → 四条）
-    评审 Minor m1）；:func:`test_the_guard_allows_the_single_seeded_root_generator` 与      ← 同上
-    :func:`test_the_global_rng_guard_allows_every_receiver_scoped_call_in_app_seed` 是两条  ← 同上
-    负对照（后者钉住「``rng.normal(...)`` 这类接收者限定的合法采样不得被误判」）。           ← 同上
-def _is_global_rng_call(text: str, imported: frozenset[str]) -> bool:                        ← 签名多了一个参数
-    全红——…故只有两种                                                                       ← _is_global_rng_call 的 docstring（两种 → 三种，本组合计 7 行）
-    2. **裸 ``<fn>``**，且 … / 导入——此时… /（空行）/ ``rng.normal(...)`` … 两种都不满足 → 放行 … / 由 :func:`…` / （样本从 ``app/seed`` 现挖）钉住。   ← 同上
-    name = parts[-1] / if name not in RNG_GLOBAL_FUNCS: / return False / return name in imported  ← 判据重排（4 行）
-    # 必须靠 ``from numpy.random import normal`` 才能与合法的 ``rng.normal(...)`` 区分开。   ← _offenders_in 的注释
-    imported_global_funcs = frozenset({ … })                                                ← 预扫改为调 _random_aliases（7 行）
-            elif _is_global_rng_call(text, imported_global_funcs):                          ← 调用点跟着改签名
```

`test_fitness.py` 是 **50 insertions / 0 deletions**——既有一条未碰。即：**没有任何一条既有 `assert` 被删除、改写、加容差、把全称量词换成存在量词、或把 `==` 换成 `in`**。既有 42 条 `FORBIDDEN_WRITINGS` 参数化用例、`_scan(app/seed) == []`、以及从 `app/seed` 现挖 **32 个**合法 `rng.*` 调用点的负对照（本轮复核仍是 32 个）全部原样保留且全绿。

#### I0.2 「生成逻辑 0 行改动」的取证

```
$ git diff --numstat 945877f..dd07ae4
27      12      backend/app/seed/fitness.py
50      0       backend/tests/seed/test_fitness.py
162     26      backend/tests/seed/test_generate.py

$ git diff 945877f..dd07ae4 -- backend/app/seed/fitness.py | 过滤掉以「# 」开头的增删行
（无输出）
```

`fitness.py` 的 27 增 12 删**逐行都是注释行**，`magnitude = w_free * max(0.0, room - profile.jitter - CORRECTION_RESERVE) / 100.0` 那一行本身一字未动（变异测试期间被临时改过一次，已还原，见 I5）。`generate.py` / `config.py` / `indicators.py` / `population.py` / `body_comp.py` / `survey.py` / `sections.py` **本轮完全未碰**。

### I1. 三个 CSV 的 SHA256（两次独立进程，逐字未变）

取证方式照简报：**不走 CLI**（`main()` 无条件既写盘又入库，会产生 `pe.db`），而是临时脚本 `%TEMP%\fix4probe\hash_probe.py` 直接调 `build_dataset(SeedConfig())` + `write_csv(...)` 写到 `%TEMP%\fix4csv\<run>\`，**两个独立进程各跑一次**（`post_a` / `post_b`）。改动**前**也同样跑了两个独立进程（`pre_a` / `pre_b`）作对照。

| 文件 | 字节数 | 基线（`945877f`，复审/fix round 3 取证值） | `pre_a` / `pre_b`（改前） | `post_a` / `post_b`（改后） | 逐字未变 |
|---|---|---|---|---|---|
| `fitness.csv` | 244496 | `498AA3256678B01A` | `498AA3256678B01A` | `498AA3256678B01A` | ✓ |
| `body_comp.csv` | 107745 | `1234025C05843B27` | `1234025C05843B27` | `1234025C05843B27` | ✓ |
| `survey.csv` | 276193 | `835A98FCC0779B51` | `835A98FCC0779B51` | `835A98FCC0779B51` | ✓ |

四次独立进程运行（改前 2 次 + 改后 2 次）三个哈希**全部逐字相同**，字节数也逐字相同。`backend/pe.db` 全程 `Test-Path` 为 `False`；`backend/data/seed/` 全程 0 个文件。

### I2. §2.1 穷举实测全表与注释逐处改动

#### I2.1 spy 探针的做法（可复现，**读生产中间状态**）

按简报 §2.1.1 与 §1 的判据，**只走「读生产代码自己构造的中间状态」这一条路径**，不重新推导任何输入。临时探针 `%TEMP%\fix4probe\probe_fix4.py` 与 `probe_fix4b.py`：

1. `monkeypatch`（直接替换模块属性）三个 spy，**每个都只做记录、然后用同一批参数原样转发给原函数**，故不额外消耗随机数：
   - `fitness._trend_labels(population, cfg, rng, bundle)` → 捕获 **`bundle`**（`_trend_inputs` 的产物，即生产代码自己构造的中间状态）与返回的 `labels`；
   - `fitness._trend_prev_targets(...)` → 捕获 `stats`（`students` / `triggered` / `total_rounds` / `max_rounds`）；
   - `fitness._settle_prev_targets(label, info, deltas, table, memo, bounds_memo)` → 捕获**逐人** `rounds`（用来查出 `triggered` 的那 19 人是谁）。
2. 调 `build_dataset(SeedConfig())`（缺省 500 人 / `seed=20250828`），跑完还原三个 spy。
3. 从捕获到的 `bundle` 里筛零宽人群：`windows["稳定"] is not None and hi - lo == 0`；再与 `labels` 取交集。
4. 穷举阶段再包一层 `fitness._classify` 的 spy，**每次 `_settle_prev_targets` 调用前清空记录、只取第一次调用的 `total_change`**——那就是 round-0 的 `Delta'`（`_settle_prev_targets` 每轮先算 `total_change` 再调 `_classify`，`_correction_move` 里那次是第二次）。`_settle_prev_targets` 直接调原函数，`table`/`memo`/`bounds_memo` 与生产同形（`memo` 是纯函数缓存，共用与重算等价）。
5. 探针用完删除，`Test-Path` 复核 `False`（见文末）。

**三个独立进程运行结果逐项一致**：`probe_fix4.py` 改动前跑一次、改动后再跑一次，`probe_fix4b.py` 跑一次；`Compare-Object` 对改动前后两次的完整 JSON 输出（剔除计时行）返回 **IDENTICAL（81 行 vs 81 行）**。

#### I2.2 实测全表

| 量 | 控制者亲验值（简报 §1） | **本轮实测** | 一致 |
|---|---|---|---|
| 校正 `triggered` / `max_rounds` | 19 / 1 | **19 / 1** | ✓ |
| 稳定类可行 | 489 | **489** | ✓ |
| 其中零宽窗口 | 133 | **133** | ✓ |
| 零宽**且**实际标为「稳定」 | 88 | **88** | ✓ |
| 波动大 / 持续下滑 / 稳步提升 全量可行 | 260 / 203 / 487 | **260 / 203 / 487** | ✓ |
| 四类标签的实际人数 | — | 波动大 75 / 持续下滑 100 / 稳步提升 125 / **稳定 200** | 与注释「200 人里」的口径一致 |
| 持续下滑 / 稳步提升 的零宽窗口数 | — | **0 / 0** | ✓ 注释「另三类一个都没有」成立 |
| 133 人的窗口取值集合 | — | **`{"(0.0, 0.0)"}`**（只有一种） | ✓ 注释「一律是 `(0.0, 0.0)`」成立 |
| 133 人的 `bmi_delta` 取值集合 | — | **`{0}`**（只有一种） | ✓ 注释「`bmi_delta` 一律为 0」成立 |

穷举（88 人 × 全部界 2 的零和抖动向量，重跑 `_settle_prev_targets`）：

| 量 | 旧注释（91 人集合，测量路径已被驳回） | **本轮实测（88 人集合）** |
|---|---|---|
| `len(free)` 分布 | — | **6 项自由 84 人 / 5 项自由 4 人** |
| 每人抖动向量数 | 1751（假定人人 6 项自由） | **1751（6 项）/ 381（5 项）** |
| 总组数 | 159341（= 91 × 1751） | **148608**（= 84×1751 + 4×381 = 147084 + 1524） |
| round-0 `Delta'` 区间 | `[−1, +6]` | **`[−1, +5]`** |
| round-0 `Delta'` 直方图 | — | `−1:29, 0:17249, 1:73625, 2:47820, 3:8603, 4:1255, 5:27` |
| 出带组数 | 110 | **27** |
| 出带的方向 | 全在 `+5` 一侧 | **全在 `+5` 一侧（高侧 27 / 低侧 0）** ✓ |
| 出带组 round-0 被判成 | 「稳步提升」 | **全部 27 组「稳步提升」** ✓ |
| 需校正组数 | 117 | **35** |
| 需校正组 round-0 被判成 | — | 稳步提升 27 + **波动大 8**（= 35，落档后凑出 3 正 3 负且 `max|delta_i'| ≥ 10`） |
| `max_rounds` | 最多 2 轮 | **最多 1 轮** |
| `RuntimeError` 次数 | 0 | **0** |
| 耗时 | — | 单趟 2.5s（`memo`/`bounds_memo` 全程共用） |

`triggered` 的 19 人里属零宽人群的人数：

| 量 | 实测 |
|---|---|
| `triggered` 人数 | **19**（`rounds` 直方图 `{1: 19}`，故 `max_rounds = 1`、`total_rounds = 19`） |
| 19 人里属**零宽人群（133）**的 | **0** |
| 19 人里属**零宽且标为稳定（88）**的 | **0** |
| 19 人的标签分布 | 稳定 **15** / 持续下滑 **4** / 波动大 0 / 稳步提升 0 |
| 19 人的「稳定」窗口 | 一律**有正宽度**：`(−2.0, 2.0)`（16 人）或 `(−1.875, 2.0)`（3 人，均为 5 项自由者） |

**结论：`triggered` 从 16 变成 19 多出的那 3 个触发者不落在零宽人群里**（19 人逐个查过，`triggered_zero_width = []`）。故注释里「生产那一轮 88 个零宽学生**一个都没触发校正**」这句**重验后仍为真**，保留，只把 `triggered = 16` 改成 `19`。

#### I2.3 注释逐处改动（行号前后对照）

`backend/app/seed/fitness.py`，`magnitude = w_free * max(0.0, …)` 上方那段注释。**只改数字与该括号段**，三条结论（「单点目标本身并不安全」`:568`、「风险因此是单边的：只有上边界会被顶穿」`:582`、「真正兜住它的是校正循环，不是这个窗口」`:584`）**一字未动**，`+6.5` 的理论推导（`:573-575`）与「把 +6.5 拉回带内最多 3 轮」（`:587`）也一字未动。

| # | 旧行号（`945877f`） | 新行号（`dd07ae4`） | 改前 | 改后 |
|---|---|---|---|---|
| 1 | `:564` | `:564` | `493 人里 **145 人**是零宽，实际被标为「稳定」的 200 人里 **91 人**是零宽` | `489 人里 **133 人**是零宽，实际被标为「稳定」的 200 人里 **88 人**是零宽` |
| 2 | `:570` | `:570` | `这 145 人的窗口一律是 ``(0.0, 0.0)``` | `这 133 人的窗口一律是 ``(0.0, 0.0)``` |
| 3 | `:575-577`（3 行） | `:575-578`（4 行） | `穷举这 91 人 × 全部 1751 个零和抖动向量（159341 组）实测：round-0 的 ``Delta'`` 落在 ``[−1, +6]``，其中 **110 组出带**（全在 ``+5`` 一侧，会被判成「稳步提升」）。` | `穷举这 88 人 × 全部界 2 的零和抖动向量实测（84 人六项自由 → 1751 个/人；4 人有一项被表下溢出钉在 ``fixed_prev`` 里、抖动只作用在余下 5 项 → 381 个/人；共 **148608** 组）：round-0 的 ``Delta'`` 落在 ``[−1, +5]``，其中 **27 组出带**（全在 ``+5`` 一侧，会被判成「稳步提升」）。` |
| 4 | `:587-589`（3 行） | `:588-591`（4 行） | `实测那 159341 组里 117 组需要校正、**最多 2 轮**、``RuntimeError`` **0 次**；生产那一轮 91 个零宽学生**一个都没触发校正**（全 500 人 ``triggered = 16``、``max_rounds = 1``）。` | `实测那 148608 组里 **35 组**需要校正、**最多 1 轮**、``RuntimeError`` **0 次**；生产那一轮 88 个零宽学生**一个都没触发校正**——全 500 人 ``triggered = 19``、``max_rounds = 1``，而那 19 人里 **0 个**属零宽人群（他们的「稳定」窗口都还有正宽度，实测 ``(−2.0, 2.0)`` 或 ``(−1.875, 2.0)``）。` |
| 5 | `:599-602`（4 行） | `:601-617`（17 行） | 「数字的口径」括号段：`145/493 … 91/200 …；复审报告写的是 133/489，本轮三条独立路径重测都是 145/493——含直接从记录的 ``score_*`` 列复算，且三个 CSV 的 SHA256 与复审时逐字相同，故数据没变。差异已作为关切上报。` | 删掉「三条独立路径重测都是 145/493」与「差异已作为关切上报」，改为**如实记录争议与裁决**：保留两个口径（133/489 是稳定类可行的人里零宽的占比、88/200 是实际被标为稳定的人里的占比，穷举用后者）；写明 fix round 3 曾测得 145/493/91、控制者与复审两轮独立测量（分别在 `945877f` 与 `bed07ed`，两者之间本文件只改过注释、生成逻辑 0 行改动，故 bundle 与三个 CSV 的 SHA256 逐字相同）均为 133/489/88；差异源于前者三条路径里有两条是「重新推导输入再调函数」（用记录的 `score_*` 列反推 `bmi_delta`、或直接调 `_delta_target_windows`），而这两条都要自己提供 `bmi_delta`，`b` 的取法一变 `lo`/`hi` 全变；**判据：读生产代码自己构造的中间状态（`_trend_inputs` 产出的 bundle）的那一次测量才算证据**（Ruling 80/81）。末尾按 §2.3 要求补上指向测试的一句：本行为由 `tests/seed/test_fitness.py` 里的 `test_zero_room_collapses_the_stable_window_to_a_single_point` 钉住，并写明改成方案 b 的后果（稳定类可行池少 133 人、洗牌与配额全变、三个 CSV 的字节与已取证哈希一并作废、须与 Task 9 一起排期） |

全文件复核：`grep -E "493|159341|110 组|117 组|triggered = 16|最多 2 轮|\[−1, \+6\]|91 人|145 人"` 在 `fitness.py` 里**只剩 1 处命中**，即 `:603` 那句刻意保留的历史记录「fix round 3 曾测得 145/493/91 并写进本注释」——它是裁决记录的一部分，不是现行数字。

### I3. §2.2 双向取证

实现（全在测试侧，`backend/tests/seed/test_generate.py`）：

- 新增 `_default_rng_targets(tree)`：收集被 `X = …default_rng(…)` 绑定的名字（`ast.Assign` 与 `ast.AnnAssign` 都覆盖），它们是**合法的根生成器**。
- 新增 `_random_aliases(tree)`：**只由 import 语句**收集两张表——`module_aliases`（`import numpy.random as npr` 的 `npr`；`from numpy import random [as rnd]` 的 `random`/`rnd`）与 `func_aliases`（`from numpy.random import <fn> [as Y]` 的 `<fn>`/`Y`，仅当 `<fn> ∈ RNG_GLOBAL_FUNCS`）。`from numpy.random import Generator` 这类非采样函数的导入**不进任何一张表**。
- `_offenders_in` 的预扫改为 `module_aliases, func_aliases = _random_aliases(tree)` + `module_aliases = module_aliases - _default_rng_targets(tree)`（**显式排除**）。
- `_is_global_rng_call(text, module_aliases, func_aliases)`：裸调用查 `func_aliases`；两段以上的接收者限定调用先查 `parts[0] in module_aliases`，再落回原有的 `np.random.<fn>` / `numpy.random.<fn>` 字面接收者规则。docstring 由「两种形状」改写为「三种形状」，并写明「别名表只能由 import 语句填充，不能由名字看起来像填充」。

**正向取证**（`%TEMP%\fix4probe\guard_evidence.py`，直接 `importlib` 载入测试模块复用同一个守卫，不重写判据；offender 全文原样贴出）：

| # | 写法 | `_scan(tmp_path)` 的 offender 全文 |
|---|---|---|
| A1 | `import numpy.random as npr` + `npr.normal(...)` | `['fake_module.py:2:npr.normal']` |
| A2 | `import numpy.random as npr` + `npr.integers(...)` | `['fake_module.py:2:npr.integers']` |
| B1 | `from numpy import random` + `random.normal(...)` | `['fake_module.py:2:random.normal']` |
| B2 | `from numpy import random as rnd` + `rnd.uniform(...)` | `['fake_module.py:2:rnd.uniform']` |
| C1 | `from numpy.random import normal as n` + `n(...)` | `['fake_module.py:from numpy.random import normal', 'fake_module.py:2:n']` |
| C2 | `from numpy.random import uniform as u, choice as c` + `u(...)` / `c(...)` | `['fake_module.py:from numpy.random import uniform', 'fake_module.py:from numpy.random import choice', 'fake_module.py:2:u', 'fake_module.py:3:c']` |

三种写法**逐条被抓**，且抓的都是**调用点那一行**（`2:` / `3:` 是行号）——C1/C2 同时保留了上一轮已有的 import 行报告，没有弄坏。这 6 条已进 `FORBIDDEN_WRITINGS`（42 → 48），参数化 id 分别是 `[42-2:npr.normal]` / `[43-2:npr.integers]` / `[44-2:random.normal]` / `[45-2:rnd.uniform]` / `[46-2:n]` / `[47-2:u]`，既有 42 条的 id 一字未变。

**负向取证**（同一探针，期望 `[]`）：

| # | 写法 | `_scan(...)` |
|---|---|---|
| N1 | 合法**局部变量** `random`：`def draw(random): return random.normal(...), random.permutation(...)`（模块里没有任何 `from numpy import random`） | **`[]`** ✓ |
| N2 | **先 import 再重绑成根生成器**：`from numpy import random` + `random = np.random.default_rng(20250828)` + `random.normal(...)`（文件名 `generate.py`） | **`[]`** ✓ |
| N3 | `from numpy.random import Generator` 只作类型标注 + `np.random.default_rng(cfg.seed)`（上一轮已有，未弄坏） | **`[]`** ✓ |
| N4 | `_scan(app/seed)`（`backend/app/seed` 全部 8 个 `*.py`，含 `__init__.py`） | **`[]`** ✓ |
| N5 | 从 `app/seed` 现挖的 **32 个**合法 `rng.*` 调用点写进假模块（`test_the_global_rng_guard_allows_every_receiver_scoped_call_in_app_seed`） | **`[]`** ✓（该测试全绿，且它的四条反空转断言 `rng.normal(` / `rng.uniform(` / `rng.permutation(` / `rng.integers(` 仍在） |

TDD 顺序：6 条新参数化用例先写、先跑出 **6 failed**（守卫对三种别名写法一律 MISSED，与上一轮探针实测一致），再实现别名表 → **52 passed**（同一 `-k` 选择下）。

### I4. §2.3 断言全文与它保护的裁定

新增 `backend/tests/seed/test_fitness.py::test_zero_room_collapses_the_stable_window_to_a_single_point`（50 行，0 删除）。断言部分全文：

```python
    curr = {item: 100 for item in WEAKNESS_ITEMS}
    windows = fitness._delta_target_windows(curr, 0, WEAKNESS_ITEMS)

    assert windows["稳定"] is not None, (
        "「稳定」窗口被判成不可行了：max(0.0, …) 钳位被改成了「余量为负即判不可行」（方案 b）。"
        "后果是稳定类可行池少 133 人、洗牌与配额全变、三个 CSV 的字节与已取证哈希全部作废——"
        "这不是一次等价重构，须与 Task 9 一起排期。"
    )
    assert windows["稳定"] == (0.0, 0.0), windows["稳定"]
    # 单点就是 b（这里 b = 0）：钳位吃掉的是 magnitude，不是窗口的位置
    assert windows["波动大"] is None and windows["持续下滑"] is None
    assert windows["稳步提升"] is not None
```

输入 `curr` 六项全 100 ⟹ `head_up = min(100 − curr) = 0` ⟹ 稳定类的 `room = min(head_up, head_down) = 0`（钳位到最狠的一格）；`bmi_delta = 0` ⟹ `b = 0` ⟹ 单点必为 `(0.0, 0.0)`。三条对照断言（波动大 `None` 因为要 `max(curr) ≤ 84`、持续下滑 `None` 因为钳位后 `lo > hi`、稳步提升仍可行因为 `room = head_down = 100`）把「方案 b 之下这名学生只剩稳步提升装得下」这件事也钉住。

**它保护的裁定**：**方案 a（接受现状，安全性押在校正循环上）**。复审建议的方案 b（把 `max(0.0, …)` 改成「余量为负即判不可行」，让 `CORRECTION_RESERVE` 名实相符）已被控制者否决。docstring 里写明了后果链：稳定类可行池立刻少 **133** 人 → `_trend_labels` 的洗牌与 `shuffled.sort` 的让位顺序全变 → 抽到的 `Delta_target` 与零和抖动全部平移 → 三个 CSV 的字节全部作废（`498AA3256678B01A` / `1234025C05843B27` / `835A98FCC0779B51` 一并失效），而收益只是让一个常量名实相符；真要改须与 Task 9（调 `jitter` / `CORRECTION_STEP` / 评分表）一起排期、一起重做可复现性取证。注释侧的互指见 I2.3 第 5 条（`fitness.py:613-617`）。

**变异验证**：把 `fitness.py:618` 改成 `magnitude = w_free * (room - profile.jitter - CORRECTION_RESERVE) / 100.0`（即去掉 `max(0.0, …)`，等价于「钳位为负即判不可行」），该断言**变红**：

```
FAILED tests/seed/test_fitness.py::test_zero_room_collapses_the_stable_window_to_a_single_point
E   AssertionError: 「稳定」窗口被判成不可行了：max(0.0, …) 钳位被改成了「余量为负即判不可行」（方案 b）。…
E   assert None is not None
```

已还原并复核 `MUTATION-TEST-TEMPORARY` 为空（I5）。

### I5. 变异测试汇总（「守卫有效」的硬证据）

三次变异，每次都跑完再全部还原：

| # | 变异点 | 变异内容 | 变红的测试 | 结论 |
|---|---|---|---|---|
| M1 | `test_generate.py::_is_global_rng_call` | `return text in func_aliases` → `return False`；`if parts[0] in module_aliases:` → `if False:`（守卫静默化） | **7 条**：新增的 6 条别名用例 `[42]`–`[47]` **全部变红**，外加既有的 `[40-2:normal]`（裸调用）也变红 | 别名表与 `func_aliases` 都是承重的；**4 条负对照全绿**（正是它们对静默化免疫，才说明自证测试不可省） |
| M2 | `test_generate.py::_offenders_in` | `module_aliases - _default_rng_targets(tree)` → `module_aliases`（去掉显式排除） | **1 条**：`test_the_guard_allows_a_local_variable_that_happens_to_be_named_random` 变红，报 `generate.py:4:random.normal` | `default_rng(...)` 赋值目标的显式排除是承重的（负对照 N2 那一半） |
| M3 | `test_generate.py::_offenders_in` | `module_aliases` → `(module_aliases \| {"random"}) - _default_rng_targets(tree)`（改成简报警告的「按名字看起来像」填充） | **1 条**：同上测试变红，报 `local_variable.py:4:random.normal` 与 `local_variable.py:4:random.permutation`；而 `_scan(app/seed)` 与 32 个现挖调用点的负对照**仍全绿** | 负对照 N1 那一半是承重的，且**只有它能抓到这个变异**——按名字猜的写法不会让任何既有测试变红 |
| M4 | `fitness.py:618` | 去掉 `max(0.0, …)`（方案 b） | **27 failed / 288 passed / 3 errors**，其中含新断言（见 I4） | 新断言变红 ✓；其余 26 条既有测试的红法见**关切 ④** |

还原复核：

```
$ Select-String -Path backend\app\seed\*.py,backend\tests\seed\*.py -Pattern "MUTATION-TEST-TEMPORARY" -SimpleMatch | Measure-Object
Count
-----
    0
```

`git diff` 也已确认 `magnitude = w_free * max(0.0, room - profile.jitter - CORRECTION_RESERVE) / 100.0` 与 `_is_global_rng_call` 的三条规则全部回到原状（还原后全量 `318 passed`、`-W error` 同样 `318 passed`）。

### I6. 关切

> 本轮四条关切**全部附可复现的测量方法**，并注明读的是生产中间状态还是自己重新推导的输入（简报 §0 最后一条、§1 的教训）。

#### 关切 ①（**简报 §2.1 的组数算错了，我按实测值写进注释**）

**原文摘要**：简报 §2.1 第 3 条要求「人数改为 88，组数随之改为 **88 × 1751 = 154088**」。这个乘法假定了 88 人**人人六项自由**，而实测**不是**：88 人里有 **4 人**只有一项被表下溢出钉在 `fixed_prev`、`free` 只有 5 项，`_zero_sum_jitter(rng, 5, 2)` 的取值空间是 **381** 个而不是 1751 个。故真实组数是 `84×1751 + 4×381 = 147084 + 1524 = `**`148608`**，不是 154088。我**没有**把 154088 写进注释——本轮存在的理由就是「不写未经实测的数字」，故按实测值写，并在注释里用一句话交代 4 人的来历（否则 148608 这个数无法被下一个人复现）。同理，旧注释的「91 × 1751 = 159341」乘法本身自洽，但 91 这个人数来自已被驳回的测量路径；若那 91 人里也有 5 项自由者，159341 同样高估。

**测量方法**（读**生产中间状态**，非重新推导）：spy 捕获 `_trend_inputs` 产出的 `bundle`（手法见 I2.1），
`Counter(len(bundle[sid]["free"]) for sid in zero_stable)` → `{6: 84, 5: 4}`；
`sum(1 for v in itertools.product(range(-2, 3), repeat=n) if sum(v) == 0)` → `n=6: 1751`、`n=5: 381`；
穷举循环里 `groups` 计数器 → `148608`。三个独立进程一致。
*（同一份 bundle 也给出 `zero_stable_free_len_distinct = [5, 6]` 与 `zero_all_free_len = {6: 129, 5: 4}`，即 133 人里同样是 4 人 5 项自由。）*

#### 关切 ②（**「110 组出带 / 117 组需校正 / 最多 2 轮」在正确人群上重测为 27 / 35 / 1，差幅远超人数差所能解释**）

**原文摘要**：人数只从 91 降到 88（−3.3%），但出带组数 110 → 27（−75%）、需校正组数 117 → 35（−70%）、`max_rounds` 2 → 1。这说明旧值不是「在同一批人上少数了几个」，而是**在性质不同的另一批人上跑出来的**——与 §1 的根因完全吻合：上一轮的 91 人集合是用重推导的 `bmi_delta` 得到的，其中若有人 `b ≠ 0`，则 `base ≠ 0`、`rounded = floor(base + 0.5) ≠ 0`，`delta_i` 就不再是纯零和抖动而是「抖动 + 一个非零平移」，出带与校正轮数都会显著放大。我这轮实测这 88 人的 `bmi_delta` **一律为 0**、窗口**一律 `(0.0, 0.0)`**，故 `base = 0`、`rounded = 0`、`delta_i` 就是抖动本身。**这不是「某处不可复现」，而是两条路径测的不是同一批人**——按 §1 的判据，读生产 bundle 的这一次胜出。

**测量方法**（读**生产中间状态**）：spy 捕获 `bundle` 后
`sorted({bundle[s]["curr_bmi"] - bundle[s]["prev_bmi"] for s in zero_all})` → `[0]`；
`sorted({str(bundle[s]["windows"]["稳定"]) for s in zero_all})` → `["(0.0, 0.0)"]`。
穷举时对每组清空并只取 `_classify` spy 的**第一次**调用（= round-0），统计 `total_change` 直方图 → `{-1:29, 0:17249, 1:73625, 2:47820, 3:8603, 4:1255, 5:27}`；`_settle_prev_targets` 返回的 `rounds > 0` 计数 → 35，`max(rounds)` → 1，`RuntimeError` → 0。三个独立进程一致（`Compare-Object` 对改前/改后两次完整 JSON 输出返回 IDENTICAL）。

#### 关切 ③（**round-0 `Delta'` 的实测上界是 +5，不是注释原写的 +6；理论界 +6.5 仍成立，故结论未撤**）

**原文摘要**：注释 `:575` 的理论推导给出 `Σ w_i·delta_i' ≤ (20+20+15+10)×10 = 650 → Delta' 最高约 +6.5`，旧注释接着写「实测落在 `[−1, +6]`」。我这轮实测上界是 **+5**（直方图里 `+6` 一组都没有）。+6.5 是对**任意** `curr` 的上界，要取到它需要四个正号项**全部**落在 60 分以下的 10 分档距上，而这 88 人的 `curr` 分布达不到那个极端；实测最高只到 +5。**因为稳定类的带是 `|Delta'| < 5`，+5 本身就已经出带**（27 组出带全部落在 `Delta' = 5`），故「单点目标本身并不安全」「风险是单边的，只有上边界会被顶穿」两条结论**继续成立，一字未撤**。我只把实测区间 `[−1, +6]` 改成 `[−1, +5]`，并**保留了 +6.5 那句理论推导**（它是结论的依据，且它作为上界没有被实测推翻）。

**测量方法**：同关切 ②（`_classify` spy 的第一次调用）。分布证据：`round0_delta_max = 5`、`round0_delta_hist` 见 I2.2、`out_of_band_high_side = 27` / `out_of_band_low_side = 0`、`round0_out_of_band_classified = {"稳步提升": 27}`。

#### 关切 ④（**简报 §2.3 的理由「没有任何测试会告诉他这件事发生了」偏强：方案 b 之下既有 310 条里有 26 条会红——但新断言仍然必要，理由要换一个**）

**原文摘要**：变异 M4（去掉 `max(0.0, …)`）的实测结果是 **`27 failed, 288 passed, 3 errors`**，其中 26 条是**既有**测试，失败原因一律是 `_trend_labels` 的响亮 `ValueError`（500 人配置：`余下 200 人应全部标为「稳定」（配额 200），但其中 17 人在该类可行域之外`；120 人配置：`余下 48 人…其中 5 人…`）。所以方案 b **不是完全静默的**，简报那句话偏强。但新断言**依然必要**，理由有两条，都比原来那条更硬：

1. **既有 26 条的失败消息会把人引到错误的地方**。它说的是「可行域筛选或配额本身与该人群的得分分布不相容」，而真正被改的是 `magnitude` 的钳位；只有新断言的消息点名了 `max(0.0, …)` 钳位、方案 b、以及「三个 CSV 的字节与已取证哈希全部作废」。定位价值在这里，不在「有没有测试会红」。
2. **那 26 条的红依赖余下池恰好溢出，是偶然而非设计**。方案 b 让稳定类可行池缩水 133 人，但 `_trend_labels` 的 `shuffled.sort(key=… windows["稳定"] is None …)` 会**优先把稳定不可行的人让给前三类**，所以大部分缩水被前三类吸收了，只有溢出的 17 人（500 人配置）触发 `ValueError`。若某次参数调整（Task 9 调 `trend_mix` / `jitter` / 评分表）让稳定池只缩水而余下池**不**溢出，方案 b 就会**静默改变全部字节而一条既有测试都不红**——那才是新断言真正堵住的洞。

**建议**：把裁定账本里方案 b 的否决理由从「没有测试会告诉他」改写成上面这两条（尤其是第 2 条的「溢出是偶然的」）。**本轮未改任何裁定文本**，只在此上报。

**测量方法**（读**生产代码的行为**，不是推导）：把 `fitness.py:618` 改成 `magnitude = w_free * (room - profile.jitter - CORRECTION_RESERVE) / 100.0`（带 `MUTATION-TEST-TEMPORARY` 标记），在 `backend/` 下跑 `pytest -q`，记录 `27 failed, 288 passed, 3 errors` 与逐条 FAILED 名字（26 条既有 + 1 条新断言），然后还原并复核 `MUTATION-TEST-TEMPORARY` 计数为 0、全量 `318 passed`。

#### 关切 ⑤（**两处陈旧自指，本轮按 §2.1「其余内容一律不动」未改，报给下一轮**）

**原文摘要**：(a) `fitness.py:558` 写「本轮按控制者裁定**只补注释、不改公式**」——那个「本轮」指的是 fix round 3，现在读到它会以为是 fix round 4；(b) `tests/seed/test_generate.py:1` 的模块 docstring 写「Task 6 仿真数据生成器的测试：**24 条** = 简报的 13 条 + 把裁定钉住的 11 条」，而该文件现在收集到 **77** 条（fix round 3 加到 70 时也没更新）。两者都是**纯文档陈旧**，不影响任何行为，改它们超出本轮授权范围，故未改。

**测量方法**：直接读文件（`fitness.py:558`、`test_generate.py:1`）；条数用 `pytest --collect-only -q tests/seed/test_generate.py` → `77 tests collected`（同法：`test_fitness.py` → 22、`test_trend_oracle.py` → 14、全量 → 318）。

### I7. 前向约束

**无新增，沿用 fix round 2 的清单**（G12 的 10 条）。本轮不改生成逻辑、不改配置、不改口径，故 G12 第 4 条的「随机流形状参数清单（六个）」一字未变。

只补一句**给 Task 9 的读数提示**（不是新约束，是 G12 第 10 条的同源信息）：本轮实测四个可行池是 波动大 **260** / 持续下滑 **203** / 稳步提升 **487** / 稳定 **489**（配额 75 / 100 / 125 / 200），**最紧的是持续下滑（203 vs 100，余量 2.03 倍）**，其次波动大（260 vs 75，3.47 倍）；稳定池 489 vs 配额 200 看着宽，但其中 **133 人（27%）的窗口是零宽单点**，方案 a 把他们的安全性全押在校正循环上。G12 第 10 条说的是「Task 9 若把人群整体推高，波动大的可行池会先枯竭」——那是针对 `max curr ≤ 84` 这一条判据的方向性判断，与本轮的绝对余量数字不矛盾，两条一起读。

### I8. 本轮 git 输出

```
$ git log --oneline -1
dd07ae4 fix: 更正零宽窗口注释里的一组错测数字，AST 守卫补 import 别名，钉住窗口退化行为

$ git status --short
（无输出：工作树干净。backend/pe.db 全程未创建（Ruling 68，每次取证后 Test-Path 复核 False）；
  backend/data/seed/ 全程保持空目录（0 个文件）；三个 CSV 的取证一律写 %TEMP%\fix4csv\；
  .superpowers/ 在 .gitignore 内，本报告与账本本来就不进版本库。）

$ git show --stat --oneline HEAD
 backend/app/seed/fitness.py         |  39 +++++---      ← 27 增 12 删，逐行都是注释（过滤注释行后 diff 为空）
 backend/tests/seed/test_fitness.py  |  50 ++++++++++     ← 50 增 0 删（§2.3 那条断言）
 backend/tests/seed/test_generate.py | 188 +++++++++++++++++++++++++++-----  ← 162 增 26 删（别名表 + 6 条自证 + 1 条负对照）
 3 files changed, 239 insertions(+), 38 deletions(-)
```

临时探针（`%TEMP%\fix4probe\probe_fix4.py`、`probe_fix4b.py`、`hash_probe.py`、`guard_evidence.py`、`commitmsg.txt`、`out1.json`、`out2.json`、`out3.json`）与临时 CSV 目录（`%TEMP%\fix4csv\pre_a` / `pre_b` / `post_a` / `post_b` 及其父目录）**已全部删除**，`Test-Path` 逐一复核为 `False`。
