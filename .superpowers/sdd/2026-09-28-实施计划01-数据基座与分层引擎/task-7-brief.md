# Task 7 派单简报 — 校内百分位快照

分支：`feature/plan-01-data-foundation`
基线 commit：`c72b53f`（工作树干净，勿 rebase、勿 reset、勿切分支）
测试基线：**318 passed**（Task 1–6 全部完成并结案）

Task 7 是本计划里最小的一个任务：一个新模块 + 一个新测试文件，**10 条测试**，不新增数据文件。计划已经过控制者预检并改过 4 处（Ruling 84–87），**照计划做即可，不要照做旧版本的印象**。

---

## 0. 环境（本项目已因这些吃过 9 次写盘事故，务必遵守）

- Windows + **PowerShell**：命令分隔用 `;`，**绝不用 `&&`**；**没有 heredoc**（多行脚本写成临时 `.py` 再 `python file.py`，**用完删掉并 `Test-Path` 复核 False**）。
- **没有 venv**。`python` / `pytest` 直接在 PATH 上。`pytest` **必须在 `backend/` 目录下跑**（`conftest.py` 与包根在那里）。
- `bash` 不在 PATH；需要时先 `$env:PATH = "C:\Program Files\Git\bin;$env:PATH"`。
- **每次编辑后必须用 shell 复核字节真的落盘**（`Select-String -Path <file> -Pattern "<刚写入的独特串>" -SimpleMatch`），不要只信编辑工具的返回值。提交前跑 `git diff --stat` 与 `git status --short`。
- **不得创建或触碰 `backend/pe.db`**（Ruling 68）。**不得往 `backend/data/seed/` 写任何东西**（它现在是空目录，保持空）。需要临时输出就写到 `%TEMP%`。
- 只提交**一个** commit。
- 做不到 / 认为计划或本简报写错了 → **写进报告的「关切」章节**，不要静默绕过、不要自作主张改设计。

> **这不是客套**：Task 6 全程实现者上报的 16 条关切里，**8 条证明是控制者自己写错了**（用 `min(gaps)` 概括整组档距分布、退化公式在 n=120 时自己违反班规模区间、把「age≥20 的比例」当成「跨龄组线的比例」、spec 判定表有一行可证明不可达、把一个实验的数字搬进另一个实验的结论、把加权和判据当成逐项判据、把连续量口径当成整数口径、写给 Task 9 的前向约束把「哪个池先枯竭」写反且药方无效）。**上报矛盾是这份工作最有价值的产出。**
>
> **但关切必须附可复现的测量方法**，并说明该方法读的是**生产代码的中间状态**还是**你自己重新推导的输入**。Task 6 fix round 3 有一条关切声称「某组数字不可复现」，控制者与复审两轮独立测量都证明是它自己的测量路径错了（重新推导 `bmi_delta` 而非读生产 bundle）——**读生产状态的那一次测量才算证据**（硬规矩 #6）。

---

## 1. 先读（顺序）

1. `Document/2026-09-28-实施计划01-数据基座与分层引擎.md` 的 **Task 7 全节**（约 `:1011`–`:1155`）——Files / Interfaces / Step 1–6。**这是本轮的权威规格，已按 Ruling 84–87 改过**。
2. 同计划的 **Global Constraints** 段（开头附近）与 **Review Focus** 段（`:34`–`:42`，其中 **#4「某性别龄组样本 < 30 人 → 降级国标常模并标记 `percentile_source = national`」就是本任务**）。
3. `Document/2026-09-28-体育闭环原型-设计spec.md` 的 **§6.3①**（短板判定 W 的定义，`P25` 是判定线）、**§4.0 / §4.2**（`AGE_GROUPS` 是年级组不是年龄段）、**§14 的 #20 / #21 / #24**。
4. `.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md` 的 **`### Task 7` 段**（`:963`–`:1000`，Ruling 84–87 的完整理由）与 **`### Task 2` 段**（`score_item` / `segment_thresholds` / `AGE_GROUPS` 的既有口径）。
5. `backend/app/domain/indicators.py`（你要消费的公开 API：`ScoredItem`、`WEAKNESS_ITEMS`、`Sex`、`AGE_GROUPS`、`score_item`、`segment_thresholds`、`StandardTable`）。
6. `backend/tests/domain/test_indicators.py` 的开头——**迷你评分表 `T` 的造法在那里**，Step 1 的 `test_national_norm_needs_no_file_beyond_the_standard_table` 要照它造一张只有 3 个档的表。
7. `backend/app/db/models.py:341-391`（`PercentileSnapshot` ORM）——你的 `PercentileRow` 要与它的业务列一一对应，`semester_id` / `computed_on` / `batch_id` 由 Task 10 落库时补，**不在你的值对象里**。
8. `backend/tests/architecture/test_domain_purity.py`——你要新建的 `app/domain/percentile.py` 会被这 3 个 AST 守卫扫描。

---

## 2. 预检已经替你排掉的 4 个坑（不要把它们又踩回去）

**① 不要创建 `backend/data/national_norm.csv`（Ruling 84）。** 旧计划要求「数值取自国标 2014 常模」，但**国标 2014 只公布评分阈值、不公布人群百分位常模**，那句话无法照做。已改为从仓内已有的 `national_standard_2014.csv` 按显式假设推导：

> 假设：全国参考人群在该项原始值上**均匀分布于表内量程** `[lo, hi]`（`segment_thresholds` 的首末阈值）。
> 得分的第 `p` 百分位 = `score_item(table, item, lo + q/100·(hi − lo), sex, age_group)`，其中 **`q = p`（越大越好）或 `q = 100 − p`（越小越好）**。

控制者已亲自跑探针验证：**24 组（6 项 × 2 性别 × 2 年级组）逆序 0 组**、全部单调不减；国标 P25 落在 **40–64**，与 500 人真实生成数据的本校 P25（**50–62**）同量级。

**方向感知是这条里承重的部分**：控制者的第一版探针没做方向感知，50 米跑与耐力跑得到 `P10=80 > P25=74 > P50=66 > P75=50` 这种**递减**序列，而 `PercentileRow` 要求 `p10 ≤ … ≤ p75`，短板判定线 `score < p25` 于是彻底失效。方向**从表推断**（比较 `score_item(lo)` 与 `score_item(hi)`），**不得按项硬编码**；`indicators._lower_is_better` 已有同一套推断但它是**私有的，不要去 import 私有名**，自己用公开 API 推一次。

**② `age_group` 的取值是年级组名，不是 `"18-19"`（Ruling 85）。** `AGE_GROUPS = ("大一、大二", "大三、大四")`（`indicators.py:71`）。旧计划测试里的 7 处 `"18-19"` 已全部改掉；如果你在任何地方看到 `"18-19"` 这种年龄段字面量，那是错的。

**③ `compute_snapshot` 不接受 `computed_on`（Ruling 86）。** `PercentileRow` 没有这个字段，收进来只能丢掉；落库时的 `semester_id` / `computed_on` / `batch_id` 由 Task 10 补。签名是 `compute_snapshot(scores, table)`。

**④ `table` 显式传参，`app/domain/percentile.py` 不得 import `app.refdata`（Ruling 87）。** 这是 Ruling 15 已为 `indicators.py` 定下的模式：domain 层保持无 I/O。两个理由：AST 纯净性守卫拦的是字面模式，拦不住「import 一个会读盘的模块」，所以纪律要靠签名强制；而且若自己 import，每条单元测试都被迫读真实 CSV，就造不出「表里只有 3 个档」这种边界形状——而那正是 Step 1 最后一条测试要测的东西。

---

## 3. 要做的

严格按计划 **Task 7 Step 1 → 6** 走，TDD 红-绿节奏：

- **Step 1**：把计划里那 10 条测试**原样**落进 `backend/tests/domain/test_percentile.py`。三条注意事项：
  - `test_national_norm_needs_no_file_beyond_the_standard_table` 在计划里是 `...` 占位，**必须真正实现**（计划注释里给了造法）。**空体测试恒绿，等于没有测试**——Task 6 刚为「守卫存在但抓不住东西」付过学费。
  - `test_fallback_row_equals_national_norm_exactly` 里 `ref.sample_size == 0` 而 `snap.sample_size == MIN_SAMPLE - 1`，两者**不等是预期的**（常模行的 `0` 表示「无样本、纯推导」，降级行覆盖为真实观测人数以满足 Review Focus #4 的留痕要求）。这一点要在 `national_norm` 与 `compute_snapshot` **两处 docstring 都写清**，否则后来人会以为其中一处写错了。
  - `PERCENTILES` 是新增的导出常量（`(10, 20, 25, 50, 75)`），五档只声明一次，`PercentileRow` 的字段与推导都从它来。
- **Step 2**：跑出 `ModuleNotFoundError: app.domain.percentile`。
- **Step 3**：**不建 CSV 文件**（见 §2①）。这一步在计划里现在是「国标常模的推导口径」，即把假设、推导式、方向感知、以及「这是占位、换真实常模时只需替换 `national_norm` 一个函数」写进 docstring。
- **Step 4**：实现 `percentile.py`。除计划正文外，注意两条：
  - **并列（ties）的后果必须写进 docstring**：就低取档使每项得分只有 ≤20 个离散取值（男引体向上仅 15 个），`method="linear"` 在大量并列处会给出 `57.5` 这类半分，而 spec §14 #21 定了 `score < p25` 用**严格小于**；叠加效果是「若某组 30% 的人同为 60 分且 P25 恰为 60，这 30% **全都不算**短板」。这是刻意口径、不是缺陷，但要写在能被看见的地方。
  - `compute_snapshot` 是**纯函数**：不碰数据库、不读盘、不碰时钟（`table` 由调用方注入）。Task 1 的 3 个 AST 守卫会扫它。
- **Step 5**：`pytest tests/domain/test_percentile.py -v` → **10 passed**；然后 `pytest -q` 全量 → **328 passed**（318 + 10），`-W error` 同样全绿。
- **Step 6**：一个 commit，message 见计划（`git add` 只含 `percentile.py` 与 `test_percentile.py`，**不含任何 CSV**）。

---

## 4. 明确不要做的事

- **不创建 `backend/data/national_norm.csv`**，也不创建任何新数据文件。
- **不改 `app/domain/indicators.py`**（Task 6 刚给它加过 `ITEM_WEIGHTS`，本轮不需要再动）。
- **不 import `app.refdata`**（Ruling 87）；测试文件里可以 import（测试不在 domain 层），生产模块不行。
- **不实现 Task 8 的任何东西**（`find_weaknesses` / `classify_trend` / `national_total` / `derive`）。`lookup_p25` 是 Task 8 要消费的接口，本轮只提供它。
- **不做物化/落库**（那是 Task 10）。
- **不碰 `backend/app/seed/`**（Task 6 已结案，任何改动都会让三个 CSV 的哈希作废）。
- 不放宽任何既有断言。基线 **318 passed**，本轮结束时既有 318 条必须仍全绿且断言未改。
- 不做本简报未要求的重构、注释补全、类型标注、额外抽象。

---

## 5. 交付

1. 一个 commit。
2. 新建报告 `.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/task-7-report.md`，包含：
   - 状态（DONE / DONE_WITH_CONCERNS / BLOCKED）与 commit 哈希；
   - 测试数（318 → ?）、`-W error` 结果、耗时；
   - Step 2 的 RED 输出（`ModuleNotFoundError`）与 Step 5 的 GREEN 输出；
   - **24 组国标常模的实测五档全表**（6 项 × 2 性别 × 2 年级组），以及「逆序 0 组」的核对结果——控制者会拿它跟自己预检时跑出的数对账（国标 P25 应落在 40–64）；
   - **`national_norm` 与 500 人真实数据本校 P25 的逐组对照**（至少 3 项 × 2 性别 × 2 年级组），确认两者同量级；
   - 三个既有 CSV 的 SHA256 是否**未被触碰**（本轮不该碰 `app/seed/`，请用 `git diff --stat c72b53f..HEAD -- backend/app/seed/` 证明为空）；
   - AST 纯净性守卫的结果（`pytest tests/architecture -v`）；
   - **变异验证**（Task 6 立下的标准做法）：至少做两次——(a) 把方向感知去掉（`q = p` 恒定），断言 `test_national_norm_percentiles_are_monotone_for_every_group` 与 `test_national_norm_direction_is_read_from_the_table_not_hardcoded` 变红；(b) 把 `MIN_SAMPLE` 的比较符从 `<` 改成 `<=`，断言 Review Focus #4 那两条变红。每次变异后**必须完全还原**并复核（例如 `git diff --stat` 为空、`Select-String` 搜变异标记为 0 命中），还原后重跑全量测试。
   - **关切章节**（照旧欢迎，附可复现方法）；
   - **前向约束章节**：至少写明 Task 8 消费 `lookup_p25` / `PercentileRow` 时需要注意的事（例如 `p25` 可能是半分、`source` 有两种取值、`sample_size` 在常模行是 0 而降级行是真实人数），以及 Task 10 落库时要补的三个列。
3. 报告写完后用 shell 复核文件存在且非空（`(Get-Item <report>).Length`），末尾附 `git log --oneline -1` 与 `git status --short` 输出（后者应为空）。
4. 临时探针全部删除，逐个 `Test-Path` 复核 False。

## 6. 最终返回给我什么

一段简明总结：状态、commit 哈希、测试数变化（318 → ?）、`-W error` 是否洁净、24 组常模的逆序组数与国标 P25 的取值范围、与本校 P25 的同量级核对结论、`git diff --stat c72b53f..HEAD -- backend/app/seed/` 是否为空、两次变异验证的结果与还原证据、**你上报的每一条关切（原文摘要 + 可复现方法）**、以及 `git status --short` 的输出。
