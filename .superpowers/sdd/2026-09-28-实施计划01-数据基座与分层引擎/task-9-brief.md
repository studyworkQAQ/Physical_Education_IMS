# Task 9 派单简报 — 红黄绿分层引擎与黄金用例

分支：`feature/plan-01-data-foundation`
基线 commit：`a1a334c`（工作树干净，勿 rebase、勿 reset、勿切分支）
测试基线：**378 passed**（Task 1–8 全部结案）

Task 9 是本计划的**算法终点**：spec §6.2 的八行决策表在这里落地，前面 8 个任务产出的 `DerivedResult` 在这里变成学生看到的红/黄/绿标签。计划已经过控制者预检并改过 **5 处**（Ruling 125–129），**照计划做，不要照旧版本的印象做**。

---

## 0. 环境（本项目已因这些吃过 12 次工具/磁盘分歧，务必遵守）

- Windows + **PowerShell**：分隔用 `;`，**绝不用 `&&`**；**没有 heredoc**（多行脚本写临时 `.py`，用完删掉并 `Test-Path` 复核 False）。
- **没有 venv**。`pytest` **必须在 `backend/` 目录下跑**。`bash` 需要时先 `$env:PATH = "C:\Program Files\Git\bin;$env:PATH"`。
- **落盘的唯一权威是 shell**：`Read` 与编辑工具的返回值**在两个方向上都不可信**（已实测过「工具报成功而磁盘没写」与「磁盘写对了而 `Read` 返回陈旧内容」两种）。判据一律用 `Get-Item.Length` + python 读字节 + `git diff`。
- **中文核对要双路**：`Select-String` 的中文模式可能给假阴性，凡用它做「应该存在/应该消失」的判定，都要有一条 python 读字节计数交叉验证。ASCII 模式不受影响，优先用。
- **追加报告用 python 二进制 `'ab'`**，不要用 `Add-Content`（PS 5.1 默认 ANSI，中文会写成乱码且不报错）。
- **`git checkout` 会把 LF 转 CRLF**，故 SHA256 跨 checkout 不可比。变异还原**不要用 `git checkout`**；判据用 `git diff --stat` 空 + 标记双路 0 命中 + 重跑全量。
- **不得创建或触碰 `backend/pe.db`**；**不得往 `backend/data/seed/` 写任何东西**（空目录，保持空）；**不碰 `backend/app/seed/`**（Task 6 已结案，改动会让三个 CSV 哈希 `498AA3256678B01A`/`1234025C05843B27`/`835A98FCC0779B51` 作废）。
- 只提交**一个** commit。
- 做不到 / 认为计划或本简报写错了 → **写进报告的「关切」章节**，不要静默绕过、不要自作主张改设计。

> **这不是客套**：Task 6 的 16 条关切里 **8 条**是控制者的错、Task 7 的 7 条里 **3 条**、Task 8 三轮的 20 条里 **10 条**，合并复审又抓出 **8 处**。**控制者累计出错 25 次，实现者累计出错 1 次。** 本轮预检也已推翻计划的一个核心预设（见 §2④：二分法调参用不上）。
>
> **每条关切必须附可复现的测量方法**，并说明读的是**生产代码的中间状态**还是**你自己重新推导的输入**（硬规矩 #6：读生产状态的那一次测量才算证据）。
>
> **另一条硬规矩（#15，Task 8 立的）**：凡一条测试要守卫的输入可能被**多道守卫**拦下，断言必须指明是哪一道（断言异常消息的特征子串，或断言某个只有该守卫会产生的副作用）。只断言「抛了某个异常类型」在这种情况下不可伪证——另一道守卫会替它兜住，测试永远绿。

---

## 1. 先读（顺序）

1. `Document/2026-09-28-实施计划01-数据基座与分层引擎.md` 的 **Task 9 全节**（约 `:1639`–`:1850`）：Files / Interfaces（含 Ruling 125/126/127/129 的口径注解）/ Step 1 的 **18 条测试** / Step 3 的实现说明 / Step 5 的 2 条集成测试 / Step 6 的 **12 个黄金用例** / Step 7。
2. 同计划的 **Global Constraints** 与 **Review Focus**（`:34`–`:42`）。
3. `Document/2026-09-28-体育闭环原型-设计spec.md` 的 **§6.1**（三处规则空洞的补齐）、**§6.2**（八行决策表，**已按 Ruling 115 把 Z0 提到第一行**）、**§6.3**、**§6.4**、**§9.2**（`:629-643`，分层可解释性的示例文案）、**§4.2**（计分项与权重表，`ITEM_DISPLAY_NAMES` 的来源）、**§14 的 #2 / #3 / #4 / #12 / #13 / #22 / #23**。
4. `.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md` 的 **`### Task 9` 段**（`:1414`–`:1466`，Ruling 125–129 的完整理由与实测分布表）与 **`### Task 8` 段末尾的前向约束**（Task 9 那 6 条）。
5. `backend/app/domain/derive.py`（`DerivedResult` / `WeaknessResult` / `BodyCompFlag` / `Trend` 的**实际字段**——`explain()` 只能引用这些）。
6. `backend/app/domain/indicators.py`（`ScoredItem` / `Sex` / `WEAKNESS_ITEMS` / `ITEM_BUCKET` / `ITEM_WEIGHTS` / `AGE_GROUPS`；本轮要给它**只增** `ITEM_DISPLAY_NAMES`）。
7. `backend/app/db/models.py:394-460` 附近（`StratificationResult` ORM，特别是 `hit_rules` 与 `percentile_source` 两列的注释）。
8. `backend/tests/architecture/test_domain_purity.py`（新建的 `app/domain/stratify.py` 会被这 3 个 AST 守卫扫描）。

---

## 2. 预检已经替你排掉的 5 个坑

**① `Z0` 是决策表的第一行，`hit_rules` 在 Z0 命中时是 `(RuleId.Z0,)` 而不是空元组（Ruling 125，承重）。**
spec §6.2 原把 `valid_count < 4` 印在**最后一行**，在「自上而下、命中即停」语义下它对 `W = 0 ∧ ¬C` 的学生**不可达**（先命中 G1 变绿）——而 `valid_count` 低恰恰由缺测造成、缺测又把 `W` 压低到 0，**最该被拦的人正好是必然被 G1 提前吃掉的人**。已改为第一行并编号 `Z0`。
计划里 `RuleId` 枚举、`RULE_ORDER`、Step 3 正文、以及 `test_insufficient_data_when_valid_count_below_4` 的断言**都已同步改过**。特别注意：**空元组会让 `explain()` 的 `hit_rules[-1]` 当场 `IndexError`**，而 Z0 恰恰是最需要向学生解释「为什么没有分层结果」的那条路径。

**② `explain()` 只能引用 `DerivedResult` 实际携带的字段（Ruling 126）。**
`DerivedResult` **不携带 P25 的数值**（`WeaknessResult` 只有 `items` / `count` / `valid_count` / `dominant_bucket`）。所以「低于校内同龄同性别 P25」是一个**固定短语**，不是数值——spec §9.2:641 的示例文案本身也只写短语。**不要为了渲染数值去扩 Task 8 的接口。**
另外三条证据来源已在计划 Step 3 写死，其中两条是坑：
- `body_comp.body_fat_pct is None`（体成分缺测）时必须渲染成「体成分数据缺失，本次不参与判定（男生阈值 20%）」这类文案，**不得渲染成 `None%`**；`limit` 一律非 None（Ruling 97②）正是为此。
- `annual_change == {}` 表示**无从比较**，不是「各项变化 0 分」（Ruling 99），文案不得渲染成后者。

**③ `ITEM_DISPLAY_NAMES` 要新建在 `app/domain/indicators.py`（Ruling 127）。**
仓内**没有任何** `ScoredItem → 中文项目名` 的映射，而 spec §9.2 的示例文案里「1000 米跑」「引体向上」都是中文名，且**名称随性别变**（男「1000 米跑」/ 女「800 米跑」；男「引体向上」/ 女「1 分钟仰卧起坐」）——靠 `item.value` 拼不出来。
类型 `dict[ScoredItem, dict[Sex, str]]`，取自 spec §4.2 的计分项列，只有上述两项随性别变、其余五项两性别同名。**对 `indicators.py` 只准增这一个常量与其测试，不得改动任何既有函数**（Task 6 增 `ITEM_WEIGHTS` 是同一先例）。测试的期望值**字面写在测试里**，不得从被测常量读回（自证循环，本项目犯过两次）。

**④ 不需要调 `latent_mean` / `latent_sd`（Ruling 128，推翻了计划的核心预设）。**
计划原文与账本 Ruling 79 都预设「要用二分法调 μ 逼近 20/45/35」。控制者跑通全链路实测（零注入、本学年 week1、学生级 P20、`national_total`/`find_weaknesses`/`flag_body_comp`/`classify_trend`/`compute_snapshot` 全部走生产代码，只有 spec §6.2 的八行表与 P20 是探针自建，Z0 在第一行）：

| 情形 | red | yellow | green | insufficient |
|---|---|---|---|---|
| **无**肌肉量 P20 线（今天的现实） | **20.2%** (101) | **44.2%** (221) | **35.6%** (178) | 0 |
| **有**肌肉量 P20 线（Task 10 之后） | **22.0%** (110) | **47.6%** (238) | **30.4%** (152) | 0 |
| spec §14 #12 目标 | 20% | 45% | 35% | — |

**两者都在 ±5% 内，缺省值已达标，二分法用不上。** 规则分布（无线）：`G1 178 / R1 87 / R2 14 / Y1 92 / Y2 65 / Y3 49 / Y4 15`；（有线）：`G1 152 / R1 102 / R2 8 / Y1 92 / Y2 95 / Y3 40 / Y4 11`。**八条规则全部有命中者**，这对黄金用例的构造有用。
`insufficient` 实测 **0 人**（零注入下无人 `valid_count < 4`），故 Z0 的黄金用例**必须手工构造**（Step 6 的 12 个用例里已含 `insufficient_data`（valid_count=3））。

**⚠️ 但 `test_target_layer_distribution_within_tolerance` 这条集成测试走的是 `stratify_dataset`（Task 10 提供），即「有线」那一组，green = 30.4%，距容差下界 30% 只剩 0.4 个百分点。** 按 Ruling 5，这条测试在本 Task 内**允许以 `ImportError` 失败**，Task 10 Step 6 才验证。所以你本轮跑不到它——但**如果 Task 10 之后它红了，先怀疑肌肉量 P20 的口径**（学生级 vs 测量行级，实测差 0.2 kg 就能翻十几个人），**不要放宽容差**。

**⑤ `StratResult.reason` 与 `explain()` 是两个东西（Ruling 129）。**
`reason` 是**由 `RuleId` 单射得出的一行规范中文名**（例如 `R1` → 「短板 ≥2 项且体成分异常」），**不含任何学生数据**，供日志、API、大屏列表使用；`explain()` 是**含具体数值的学生端长文案**。**判据**：`reason` 必须能只从 `RuleId` 算出来（`stratify` 里一张 8 行的映射表），若它需要读 `derived` 就说明职责串了。

---

## 3. 要做的

严格按计划 **Task 9 Step 1 → 7** 走，TDD 红-绿：

- **Step 1**：把计划里那 **17 条** `test_stratify.py` 测试原样落地（`mk()` 助手已在 Ruling 116 修好，**逐字照抄即可**），再加 **1 条** `ITEM_DISPLAY_NAMES` 与 spec §4.2 逐行一致的测试 → **18 条**。
- **Step 2**：跑出 `ModuleNotFoundError: app.domain.stratify`。
- **Step 3**：实现 `stratify.py`。`app/domain/stratify.py` 不得有任何 I/O、不得 import `app.refdata`、不得碰时钟（AST 守卫会拦）。
- **Step 4**：`pytest tests/domain/test_stratify.py -v` → **18 passed**；全量 `pytest -q` → **396 passed**（378 + 18），`-W error` 同样全绿。
- **Step 5**：写 `tests/integration/test_golden_cases.py` 的 2 条集成测试。**按 Ruling 5，它们在本 Task 内允许以 `ImportError: app.pipeline.run_stratify` 失败**——那是 Task 10 的产物，**不要为了让它绿而自己造一个 `stratify_dataset`**（Step 7 明文禁止）。
- **Step 6**：落地 `tests/fixtures/golden_cases.json`，**12 个手工构造用例**，逐条覆盖计划列的清单（R1 / R2 / Y1×2 / Y2 / Y3×2 / Y4 / G1 / `insufficient_data`(valid_count=3) / 男体脂率 20.0% 边界 / 女体脂率 28.1% 边界），每条含 `note` 字段说明构造意图。**输入是 6 个短板判定项的原始值 + 体成分 + 上学年成绩，不是已算好的 W/C**——必须走完整链路才有回归价值（spec §1.3 逐人可追溯、§12 黄金用例是「算法可复现」的直接证据）。
  **构造提示**：控制者实测的规则分布可以直接当靶子用——例如要造 R2（`W ≥ 4` 且 `¬C`）就让 4 项原始值远低于该组 P25、体脂率放在阈值以下；要造 Y4 就让 `W = 0`、`¬C`、且两学年总分下降 ≥5（`Trend.DECLINING`）。**P25 用生产 `compute_snapshot` 在这 12 人自己的数据上算**，不要手抄一个数——手抄会让黄金用例与快照口径脱钩。
- **Step 7**：`pytest tests/domain/test_stratify.py -v` → **18 passed**；`pytest tests/integration -v` → **预期 ERROR**（`ModuleNotFoundError: app.pipeline.run_stratify`），这是 Ruling 5 明写的已知状态，**不得为此在 Task 9 内实现 `run_stratify`**。

### 变异验证（必做，本项目立下的标准做法）
至少四次，每次**必须完全还原并三重取证**（`git diff --stat` 空 + 标记双路 0 命中 + 还原后重跑 396）：
1. **`RULE_ORDER` 把 `Z0` 移到最后**（复现 spec 原来的错序）→ `test_insufficient_data_beats_all_rules` 应变红。
2. **`R1` 与 `R2` 互换顺序** → `test_R1_takes_priority_over_R2` 应变红。
3. **`Y4` 的趋势判据从 `is Trend.DECLINING` 改成 `is not Trend.IMPROVING`**（即「非提升就升级」）→ `test_Y4_does_not_fire_for_volatile_or_improving` 应变红。
4. **`hit_rules` 在 Z0 命中时返回空元组**（复现计划原文的错） → `test_insufficient_data_when_valid_count_below_4` 应变红，**且 `explain()` 那条断言应以 `IndexError` 或类似形式失败**——这一次变异要同时验证「测试能抓到」与「原文那个错真的会崩」。

**如果某次变异没有让任何测试变红，说明守卫是空转的——这是本轮最重要的发现类型，必须上报。**

---

## 4. 明确不要做的事

- **不实现 Task 10 的任何东西**（`app/pipeline/run_stratify.py` / `stratify_dataset` / `daily.py` / `extract.py` / `percentile_stage.py`）。Step 5 的 2 条集成测试**允许红**。
- **不调 `latent_mean` / `latent_sd`**（Ruling 128：缺省值已达标）。也不改 `SeedConfig` 的任何缺省值。
- **不碰 Ruling 102 / 120 / 121**（肌肉量 P20 无生产者、`percentile_source` 无生产者、`SnapshotMetric`）——已裁定留到 **Task 10 预检**。本轮黄金用例若需要肌肉量 P20，**在 fixture 里手工给定该组学生的 P20 值并在 `note` 里写明**，不要去改 `percentile.py`。
- 对 `app/domain/indicators.py` **只增 `ITEM_DISPLAY_NAMES` 与其测试**，不改任何既有函数与常量。
- 不动 `app/domain/derive.py`、`app/domain/percentile.py`、`app/seed/`、`app/pipeline/`、`app/db/`、`app/adapters/`。
- 不放宽任何既有断言。基线 **378 passed**，本轮结束时既有 378 条必须仍全绿且断言未改。
- 不新增计划未列的导出符号（`Layer` / `RuleId` / `RULE_ORDER` / `MIN_VALID_COUNT` / `W_RED_UNCONDITIONAL` / `StratResult` / `stratify` / `explain` + `ITEM_DISPLAY_NAMES`，就这些）。
- 不做本简报未要求的重构、注释补全、类型标注、额外抽象。

---

## 5. 交付

1. 一个 commit，message 形如：
   `feat: 红黄绿分层引擎与 12 个黄金用例，Z0 数据不足闸门置于决策表首行`
2. 新建报告 `.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/task-9-report.md`，含：
   - 状态（DONE / DONE_WITH_CONCERNS / BLOCKED）与 commit 哈希；
   - 测试数（**378 → 396**，其中 `test_stratify.py` 18 条 + `test_golden_cases.py` 2 条**预期 ImportError**）、`-W error` 结果、耗时；
   - Step 2 的 RED 输出、Step 4 的 GREEN 输出、**Step 7 的 `tests/integration` ERROR 输出**（这是 Ruling 5 要求的已知状态，必须原样贴出来）；
   - **八条规则在 12 个黄金用例上的命中矩阵**（哪个用例命中哪条规则、`hit_rules` 全文），用以证明 12 个用例真的覆盖了八行；
   - `explain()` 在**四条代表路径**上的实际输出全文：R1（体脂超标 + 短板）、Y4（趋势升级）、G1（全清）、**Z0（数据不足）**，以及**体成分缺测**（`body_fat_pct is None`）时不得出现 `None%` 的证据；
   - `reason` 的 8 行映射表全文（证明它只依赖 `RuleId`、不含学生数据）；
   - `ITEM_DISPLAY_NAMES` 的完整内容 + 它与 spec §4.2 逐行对照的表；
   - **四次变异验证的结果**（各红几条、哪几条、失败消息要点）与三重还原证据；
   - `git diff --stat a1a334c..HEAD`（应为 `stratify.py` + `test_stratify.py` + `test_golden_cases.py` + `golden_cases.json` + `indicators.py` + `test_indicators.py` 六个文件），以及 `-- backend/app/seed/ backend/data/` 为空的证明；
   - AST 守卫结果（`pytest tests/architecture -v`）；
   - **关切章节**（每条附可复现方法 + 说明读的是生产状态还是重新推导）；
   - **前向约束章节**：至少写明 Task 10 消费 `stratify` / `StratResult` 的注意事项（`hit_rules` 是「已评估序列」而非「命中集合」、`reason` 不含学生数据故可直接入库、`percentile_source` 该怎么填——Ruling 120 说它在 `valid_count = 0` 时无定义、控制者已裁定填 `"none"` 并需扩 ORM 的 CHECK 取值域）。
3. 报告写完后 shell 双路复核文件存在且非空，末尾附 `git log --oneline -1` 与 `git status --short`（应为空）。
4. 临时探针全部删除，逐个 `Test-Path` 复核 False。

## 6. 最终返回给我什么

一段简明总结：状态、commit 哈希、测试数变化（378 → ?）、`-W error` 是否洁净、Step 7 的 ImportError 是否如 Ruling 5 预期、**八条规则的黄金用例命中矩阵**、四条代表路径的 `explain()` 输出摘要、`reason` 映射表、四次变异验证结果与还原证据、`git diff --stat` 与 `app/seed/` 为空的证明、**你上报的每一条关切（原文摘要 + 可复现方法）**、以及 `git status --short` 的输出。
