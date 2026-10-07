# Task 6 — Fix Round 2 派单简报

分支：`feature/plan-01-data-foundation`
基线 commit：`3b10f5e`（工作树干净，勿 rebase、勿 reset、勿切分支）

上一轮任务评审判 **FAIL**（2 Critical / 5 Major）。控制者已独立复核，评审成立，且追到了比评审更深的根因：**spec §6.3 的趋势判定表自己有一行不可达**。规格已改完并提交（`f40d294`、`3b10f5e`），本轮是把代码对齐到新规格。

本轮落实 **Ruling 62 / 63 / 64 / 65 / 66 / 67 / 68 / 69** 与 4 条 Minor。裁定全文见 `.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md` 的 `### Task 6` 段末尾。

---

## 0. 环境（务必逐条遵守，本项目已因这些吃过 9 次写盘事故）

- Windows + **PowerShell**。命令分隔用 `;`，**绝不用 `&&`**。**没有 heredoc**——多行脚本写成临时 `.py` 文件再 `python file.py`，**用完删掉**。
- **没有 venv**。`python` / `pytest` 直接在 PATH 上。`pytest` **必须在 `backend/` 下跑**。
- `bash` 不在 PATH；需要时先 `$env:PATH = "C:\Program Files\Git\bin;$env:PATH"`。
- **每次编辑后必须用 shell 复核字节真的落盘了**（`Select-String -Path <file> -Pattern "<刚写入的独特串>" -SimpleMatch`）。不要只信编辑工具的返回值。提交前 `git diff --stat` + `git status --short`。
- **不得触碰 `backend/pe.db`**（Ruling 68）。它已被控制者删除（此前被混合 seed 的取证污染成 596 名学生）。本轮所有取证一律 `--out-csv` 到**临时目录**、**不跑入库分支**。若你的探针必须入库，用 `tmp_path` 或临时目录里的独立 db 文件，用完删掉。
- 任何**你无法做到的事、或简报里你认为写错了的地方**，不要静默绕过、也不要自作主张改设计：照做你能做的部分，把问题写进报告的「关切」章节。

> **上一轮的教训值得你知道**：你在 fix round 1 上报的 7 条关切里，**3 条证明是控制者自己写错了**（Ruling 59 我用 `min(gaps)` 概括了整组档距分布、Ruling 60 我写的退化公式在 n=120 时自己违反班规模区间、Ruling 61 我把「age≥20 的比例」当成了「跨龄组线的比例」）。本轮评审又抓出 2 条（Ruling 67 数字搬错实验、Ruling 63 总分口径写成了 600 分制）。**继续上报矛盾，这是这份工作里最有价值的产出。**

---

## 1. 先读这些（顺序）

1. `.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/task-6-review.md` —— 评审报告全文（57951 字节），特别是 `## 缺陷` 的 C1/C2 与 M1–M5，以及 `## 控制者必须裁定的事项`。**不要跳读 Minor 段**，本轮要修其中 4 条。
2. `Document/2026-09-28-体育闭环原型-设计spec.md` 的 **§6.3（趋势，已重写）**、**§10.5（已重写）**、§4.2 的权重表、§14 的 #22/#23。
3. `Document/2026-09-28-实施计划01-数据基座与分层引擎.md` 的 **Task 6 Step 4（已重写，`:883`–`:920` 附近）** 与 **Task 8 的 Interfaces + Step 1 趋势测试（`:1074`–`:1200` 附近）**。Task 8 的部分本轮**不实现**，但你必须读——它是你写的 oracle 测试将来要对账的对象，口径必须一致。
4. `progress.md` 的 `### Task 6` 段末尾（Ruling 62–69 + 前向约束 + 控制者错误模式）。
5. 你自己的 `task-6-report.md`（`## Fix Round 1` 在第 336 行之后）。
6. `backend/app/seed/fitness.py`、`backend/app/seed/config.py`、`backend/app/domain/indicators.py`。

**架构红线**：`app/domain/` 禁止任何 I/O、禁止 `import random`、禁止时钟调用（AST 守卫会拦）。本轮**允许且需要**改 `app/domain/indicators.py`，但**只准加 `ITEM_WEIGHTS` 常量与它的测试**，不得改动任何既有函数的行为。`app/seed/` 内禁止第二个 `default_rng` / `np.random.seed` / `import random` / `date.today`。

---

## 2. 缺陷现状（控制者已亲验，不是转述）

控制者写探针按 `trend_label` 分组算「本学年 week1 六项总分 − 上学年 week1 六项总分」：

| 标签 | n | 均值(本−上) | 正数占比 | 中位 |
|---|---|---|---|---|
| 持续下滑 | 100 | **+54.17** | **100.00%** | +54.0 |
| 波动大 | 75 | +8.71 | 57.33% | +15.0 |
| 稳步提升 | 125 | **−47.52** | **0.00%** | −49.0 |
| 稳定 | 200 | +0.79 | 46.00% | 0.0 |

**「持续下滑」与「稳步提升」完全互换。** 根因：`fitness.py:566` 的 `target -= offsets[...]` 与同文件 `:144-146` docstring 明写的约定（「上学年得分 = 本学年得分 + U(*prev_offset)」，偏移为正表示上学年更好）符号相反。它能活过两轮 236 条测试，是因为 `trend_label` 在全部测试里**只被数过一次个数**，没有任何一条钉住方向（M5）。

注意（Ruling 63）：上表用的是**六项之和**（0–600），这只是控制者的诊断口径。**规格口径是国标加权总分（0–100）**，你修完后必须按加权口径复算这张表并写进报告。

---

## 3. 要做的改动

### 3.1 Ruling 63 —— `ITEM_WEIGHTS` 与总分口径

在 `backend/app/domain/indicators.py` 增一个模块级常量（**只加常量，不动任何函数**）：

```python
ITEM_WEIGHTS: dict[ScoredItem, int] = {
    ScoredItem.BMI: 15,
    ScoredItem.VITAL_CAPACITY: 15,
    ScoredItem.SPRINT_50M: 20,
    ScoredItem.SIT_AND_REACH: 10,
    ScoredItem.STANDING_JUMP: 10,
    ScoredItem.PULL_UP_OR_SIT_UP: 10,
    ScoredItem.DISTANCE_RUN: 20,
}
```

取自 spec §4.2 的权重表，和为 100。**它是全仓唯一的权重所有者**：Task 8 的 `national_total`、Task 10 的总分入库、以及你本轮的趋势定标都必须用它，不得手抄第二份。docstring 要写明「与 spec §4.2 逐行对应；国标总分 = `Σ w_i × score_i // 100`（0–100）」。

在 `backend/tests/domain/test_indicators.py` 增测试：
- 七个键**恰好**是 `ScoredItem` 的全部成员（不多不少）；
- 求和 `== 100`；
- 逐项与 spec §4.2 的字面值一致（把期望值写在测试里，**不要从 `ITEM_WEIGHTS` 读回来跟自己比**——那是自证循环，上一轮就有一个测试犯了这个毛病，见评审 Minor）。

**本轮不实现 `national_total`**（它属 Task 8 的 `derive.py`）。你在生成器里需要一个局部函数算加权总分；请把它写成 `app/seed/fitness.py` 里的**私有** `_weighted_total(scores: dict[ScoredItem, int]) -> int`，并在 docstring 里注明「Task 8 会提供生产版 `national_total`，届时本函数应删除并改用它」，同时在报告的「前向约束」里记一条。**不要在 `app/seed/` 里导出一个公开的总分函数**——那会变成第二个所有者。

### 3.2 Ruling 62 + 64 + 65 —— 重写趋势模型

**先把 spec §6.3 的新判定表逐字读懂**（行序、口径、两条勘误、`delta_i = 0` 的保守处置）。判定顺序是 **波动大 → 持续下滑 → 稳步提升 → 稳定**，命中即停。

然后按计划 **Task 6 Step 4** 的正文重写 `fitness.py` 的趋势部分。要点（计划里有完整版与理由，此处只列骨架）：

1. **`TREND_PROFILES` 整体重定义**。现在的 `prev_offset`（「上学年更好为正」）语义与新规格的 `delta_i`（「本学年更好为正」）**符号相反**，所以**不能只把 `:566` 的 `-=` 改成 `+=`**——那样只是把错误从一处挪到另一处。改为按标签给出 `Delta_target` 的抽样区间与逐项模式（计划 Step 4 的表格）。
2. **均匀分配**，不是 `1/w_i` 反比（计划里写了为什么：反比会让 w=10 的项承担 33 分摆幅，不可行也不像整体衰退）。叠一个**和为零**的逐项抖动。
3. **先扣 BMI 贡献**：先算出上学年的 BMI 得分，`Delta_6 = Delta_target − w_bmi × delta_bmi / 100`，再把 `Delta_6` 分配到六项。BMI 占 15% 权重，一次 1.2 kg 的年度体重漂移就能贡献 ±3 分，足以把一个「稳定」学生推过 ±5 线。
4. **落档 → 重算 → 校正**（计划 Step 4 的 4 步，承重）。国标 60 分以下档距是 10 分，就低取档单项最多吃掉 9 分、六项加权最多约 7.65 分——与「稳定」类的 ±5 窄带同量级，**靠留余量躲不过去**，必须落档后用整数精确重算 `Delta'`，不达判据就把权重最大的那一项再推一个官方档。循环**单调且有界**（上限 8 轮），超限 `RuntimeError` 响亮失败。
5. **可行域筛选的配额分配**：顺序 `波动大`（最受限，判据 `min curr ≥ 16 且 max curr ≤ 84`）→ `持续下滑` → `稳步提升` → 余下给 `稳定`。各从自己的可行池按 `allocate_quota` 抽取，**池不足时 `ValueError` 报出需要数与实有数**，不得静默改标签。
6. **与 Ruling 58 的表下溢出协同**：被标记学生的 `pull_up_or_sit_up` 的 `delta` 由溢出逻辑固定（地板效应），趋势模型只在其余五项上分配，且第 3 步的 `Delta'` 必须把这一项的固定贡献算进去。
7. **删除 `_trend_offsets` / `ITEM_TREND_JITTER_SD` / `PREVIOUS_YEAR_WEIGHT_SHIFT` 里与新模型冲突的部分**。`PREVIOUS_YEAR_WEIGHT_SHIFT` 保留（它是体重的年度漂移，不是得分偏移）。`N(0, 0.6)` 那种「方差还是标准差」的含糊记法（评审 Minor）随重写一并消除。

**Ruling 56 的龄组、Ruling 54/57/58 的抖动与表下溢出逻辑一律保持不动**——它们上一轮已验收通过，本轮只改趋势模型。但趋势重写会改变随机流，所以它们的**观测量会变**，报告里要重新给数。

### 3.3 Ruling 69① —— oracle 测试（本轮最重要的一条）

新增 `backend/tests/seed/test_trend_oracle.py`：

- 在**测试文件里**按 spec §6.3 的四行判据（含行序、含 `delta_i = 0` 两边都不计入的保守处置）独立实现一个 `_oracle(deltas: dict, total_change: float) -> str`。**必须直接从 spec 的表格文字翻译，不得从生成器的代码里抄逻辑**——否则它是自证循环，抓不住任何东西。
- **至少 6 条手算黄金用例**，逐条覆盖：波动大优先于持续下滑（3 项各降 12 + 3 项各升 10，必须判波动大）、只由总分分支触发的持续下滑、只由「≥3 项降 ≥5」分支触发的持续下滑、稳步提升、稳定、以及「有一项 `delta = 0` 导致波动大退化不可达」。每条的期望值**在注释里写出算式**（例如 `Σ w·d = 20×−12 + 20×−12 + 10×−12 + 15×10 + 10×10 + 10×10 = −250 → Delta = −2.5`），使读者能独立复核。计划 Task 8 Step 1 里已经有 10 条同口径的测试草稿（`:1109`–`:1190`），**可以直接借用它们的构造**，但期望值要你自己按 spec 重算一遍再用，不要照抄。
- **500 人全覆盖**：`build_dataset(SeedConfig())` 取两学年的 `week1` 记录，按 `student_id` 配对，逐人断言 `_oracle(实际 delta, 实际 Delta) == record["trend_label"]`。实际 `Delta` 用 `_weighted_total` 从**记录里的得分列**算，不要用生成器的中间变量（否则又是自证）。
- 一条**方向回归测试**（M5 的直接守卫）：按 `trend_label` 分组，断言「持续下滑」组的 `Delta` **中位数 < 0 且负数占比 ≥ 95%**、「稳步提升」组**中位数 > 0 且正数占比 ≥ 95%**。这条测试在改动前必须**红**，改动后必须**绿**——报告里贴出改动前的失败输出。
- 一条**四类都非空**的测试：`波动大` 组人数 `== 75`（`allocate_quota` 精确配额），且该组每人都满足「恰好 3 正 3 负 + `max|delta| ≥ 10`」。这是 C2「波动大不可达」的直接守卫。

### 3.4 Ruling 66 —— 补 `latent_sd`

`SeedConfig` 增 `latent_sd: float = 1.0`，`latent_profiles` 里 `rng.normal(cfg.latent_mean, cfg.latent_sd, total)` 用上它（现在是硬编码 `1.0`）。加一条测试：`latent_sd` 改变时潜变量的经验标准差随之改变（例如 `latent_sd=2.0` 时 `std(fitness)` 落在 `[1.8, 2.2]`）。**不要**在本轮做二分法调参（那是 Task 9）。

### 3.5 四条 Minor（本轮一并修，都便宜且都是守卫类）

1. **AST 随机源守卫补两种写法**：`datetime.datetime.now()`（注意 `import datetime as dt` 后写作 `dt.datetime.now()` 也要能抓住）与 `Generator(PCG64(...))` / `np.random.Generator(...)` 这类「自己造一个生成器」的写法。**并为每一种被禁写法加一条自证测试**：把违规源码写进 `tmp_path` 下的假模块，断言守卫函数对它返回违规。守卫抓不住任何东西比没有守卫更危险——上一轮就有一个测试因为「期望值从被测常量读回来」而完全无效（评审 Minor）。
2. **`inject_dirty` 的 `_cell` 对 `np.float64` 会写坏单元格**：显式转 Python 标量（`float()` / `int()`），并加一条测试：注入前把某列全换成 `np.float64`，断言注入后的值仍是 Python 标量且 `repr` 里不含 `np.float64(`。
3. **`fitness.py:28` 的 docstring 撒谎**：它称自己是「`app.seed` 里唯一会碰磁盘的地方」，实际磁盘 I/O 在 `generate.py`，本模块只经 `app.refdata.standard()`。更正。
4. **`TREND_PROFILES` 的 `N(0, 0.6)` 记法**随 3.2 的重写消除。

---

## 4. 明确不要做的事

- 不实现 Task 8 的 `classify_trend` / `national_total` / `derive`（Ruling 69② 的对账测试属 Task 8）。本轮只写**测试内的 oracle**。
- 不改 `app/domain/indicators.py` 里任何既有函数（`score_item` / `raw_from_score` / `segment_thresholds` / `age_group_of` / `_lower_is_better`），只加 `ITEM_WEIGHTS`。
- 不改 Ruling 54/57/58 的抖动与表下溢出逻辑，不改 Ruling 55/60 的编班，不改 Ruling 56 的龄组逻辑。
- 不做 `latent_mean` / `latent_sd` 的二分法调参（Task 9）。
- 不动 `write_csv` 的三文件契约、`allow_nan=False`、`make_batch_key`、日期零填充（Ruling 35/36/37/38/39）。不加 `students.csv`。
- 不碰 `backend/pe.db`（Ruling 68）。
- 不拆 `generate.py`（上一轮关切 ⑧ 已裁定接受）。
- 不做本简报未要求的重构、注释补全、类型标注。
- 不修评审列出的**其余 4 条延后 Minor**（过期观测量、`target_layer_dist` 死配置、duplicate 副本堆末尾、一条测试末尾挂无关断言）——它们已进账本交终审，本轮修了只会让评审 diff 变大。

---

## 5. 交付

1. 全部改动提交为**一个** commit，message 形如：
   `fix: 重写趋势模型使其满足 spec 6.3 判定表，补 ITEM_WEIGHTS 与 oracle 测试`
   正文列出 Ruling 62–69 与关键实测数字。
2. 把本轮内容**追加**到 `.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/task-6-report.md` 末尾（新章节标题 `## Fix Round 2`）。**只追加，不要重写整个文件**（现已 66913 字节）。报告须含：
   - **方向回归测试改动前的失败输出**（3.3 要求的那一条）；
   - 按**加权总分口径**复算的四类标签分组表（对应 §2 那张表，但用 0–100 口径）；
   - oracle 测试的 500 人全覆盖结果：四类各多少人、`_oracle` 与 `trend_label` 的不一致数（必须为 0）；
   - 校正循环的触发统计：多少学生触发了校正、最大迭代轮数、`RuntimeError` 次数（必须为 0）；
   - 可行域筛选的池大小：`波动大` 池多少人 / 需要 75 人，`持续下滑` 与 `稳步提升` 的池大小；
   - 新旧测试数（基线 **236** → 新值）；`-W error` 结果与耗时；
   - 三个 CSV 的新 SHA256 前 16 位（两次独立 CLI 进程 + `seed=1` 差异性），**取证一律走临时目录，不碰 `pe.db`**；
   - 相关系数、肺活量不同取值个数、被标记男生数与 `strength_count` 分布的**新值**（趋势重写会平移随机流）；
   - 4 条 Minor 的修法与各自的自证测试；
   - **关切章节**（照旧欢迎，上一轮 7 条里 3 条证明是控制者错了）；
   - **前向约束章节**：至少包含 `_weighted_total` 应在 Task 8 删除改用 `national_total`、四类标签修好后 Y4 触发人群会大幅变化（此前 46% 判持续下滑是缺陷产物，修好后应接近配置的 20%）、以及随机流形状参数清单已增至五个。
3. 报告写完后用 shell 复核文件确实变长（`(Get-Item <report>).Length`），末尾附 `git log --oneline -1` 与 `git status --short` 输出（后者必须为空，除了 `.superpowers/` 内的东西——它在 `.gitignore` 里，本来就不显示）。
4. 临时探针文件全部删除。

---

## 6. 如果本轮做完趋势仍不达判据

这是最可能出问题的地方。**不要为了让测试通过而放宽 oracle**（那是把缺陷藏起来）。按以下顺序处理：

1. 先怀疑**可行域筛选**：池筛得不够严，导致校正循环推不动。把筛选判据收紧再试。
2. 再怀疑**BMI 贡献扣除的顺序**：必须在抽 `delta_i` 之前就知道上学年的 BMI 得分，而上年 BMI 依赖上年身高体重——如果现在的代码顺序是「先抽六项、后算身高体重」，就要调整生成顺序。这是本轮最可能的结构性障碍，**如果它迫使你把 `make_fitness_tests` 的记录循环拆成两趟（先算全部身高体重与 BMI，再算六项），那就拆**，这属于必要改动。
3. 仍不行 → **上报关切并停手**，不要私自改 spec 的阈值或行序。规格刚因为「有一行不可达」改过一次，再改必须由控制者做可达性验证。
