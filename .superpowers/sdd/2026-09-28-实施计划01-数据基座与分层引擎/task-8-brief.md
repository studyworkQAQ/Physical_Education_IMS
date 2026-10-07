# Task 8 派单简报 — 派生指标（趋势 / 短板 / 体成分异常）

分支：`feature/plan-01-data-foundation`
基线 commit：`23f3468`（工作树干净，勿 rebase、勿 reset、勿切分支）
测试基线：**328 passed**（Task 1–7 全部结案）

Task 8 是本计划的**算法核心之一**：它把「国标得分 + 校内百分位 + 体成分 + 历史成绩」压成 Task 9 分层引擎要吃的三个变量（趋势 `Trend`、短板 `WeaknessResult`、体成分 `BodyCompFlag`）。计划已经过控制者预检并改过 **7 处**（Ruling 95–101），**照计划做，不要照旧版本的印象做**。

---

## 0. 环境（本项目已因这些吃过 11 次写盘事故，务必遵守）

- Windows + **PowerShell**：命令分隔用 `;`，**绝不用 `&&`**；**没有 heredoc**（多行脚本写成临时 `.py` 再 `python file.py`，**用完删掉并 `Test-Path` 复核 False**）。
- **没有 venv**。`python` / `pytest` 直接在 PATH 上。`pytest` **必须在 `backend/` 目录下跑**。
- `bash` 不在 PATH；需要时先 `$env:PATH = "C:\Program Files\Git\bin;$env:PATH"`。
- **每次编辑后必须用 shell 复核字节真的落盘**。判据是 `Get-Item.Length` 与 `LastWriteTime` **是否真的变了**，不是编辑工具的返回值、也不是 `Read` 的结果（Task 7 已实测：对**同一已存在文件的第二次及以后写入**可能两个工具都报成功、`Read` 也读到新内容，磁盘上却仍是旧版）。若发现没落盘：`Remove-Item` 删掉（`Test-Path` → False）后按**新文件**重写。
- **中文核对要双路**：`Select-String` 的中文模式在某些会话状态下会给假阴性，故凡用它做「应该存在 / 应该消失」的判定，**都要有一条独立的 python 读字节计数作交叉验证**（Ruling 94）。
- **追加报告用 python 二进制模式，不要用 `Add-Content`**（PS 5.1 的 `Add-Content` 默认 ANSI，会把中文写成乱码**且不报错**）。
- **不得创建或触碰 `backend/pe.db`**（Ruling 68）；**不得往 `backend/data/seed/` 写任何东西**（空目录，保持空）；**不碰 `backend/app/seed/`**（Task 6 已结案，任何改动都会让三个 CSV 的哈希 `498AA3256678B01A` / `1234025C05843B27` / `835A98FCC0779B51` 作废）。
- 只提交**一个** commit。
- 做不到 / 认为计划或本简报写错了 → **写进报告的「关切」章节**，不要静默绕过、不要自作主张改设计。

> **这不是客套**：Task 6 全程实现者上报 16 条关切，**8 条证明是控制者写错了**；Task 7 上报 7 条，**又有 3 条是控制者的错误**（把探针输出里的国标 P25 下界 30 抄成 40、漏写本校 P25 的切片条件、凭推理预测变异结果而没实跑、写错既有代码的去重键）。**上报矛盾是这份工作最有价值的产出。**
>
> **但每条关切必须附可复现的测量方法**，并说明该方法读的是**生产代码的中间状态**还是**你自己重新推导的输入**——Task 6 有一条关切声称「某组数字不可复现」，两轮独立测量都证明是它自己的测量路径错了（重新推导 `bmi_delta` 而非读生产 bundle）。**读生产状态的那一次测量才算证据**（硬规矩 #6）。

---

## 1. 先读（顺序）

1. `Document/2026-09-28-实施计划01-数据基座与分层引擎.md` 的 **Task 8 全节**（约 `:1170`–`:1530`）：Files / Interfaces（含 Ruling 97–101 的口径注解）/ Step 1 的 **34 条测试**（控制者已逐条实跑验证期望值）/ Step 3 的实现说明 / Step 4–5。
2. 同计划的 **Global Constraints** 与 **Review Focus**（`:34`–`:42`，其中 **#2「单项缺失导致 `valid_count` 变化，缺失项绝不当 0 分」就是本任务**）。
3. `Document/2026-09-28-体育闭环原型-设计spec.md` 的 **§6.3（三个输入变量的精确定义，含判定表行序、口径、符号约定、两条勘误）**、**§6.4（主导短板）**、**§4.2（7 计分项 / 6 短板判定项 / 权重表）**、**§14 的 #16 / #20 / #21 / #22 / #23**。
4. `.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/progress.md` 的 **`### Task 8` 段**（`:1084`–`:1128`，Ruling 95–101 的完整理由）与 **`### Task 6` 段末尾的前向约束清单**（Task 8 那一条是给你的）。
5. `backend/app/domain/indicators.py`（`ScoredItem`、`WEAKNESS_ITEMS`、`ITEM_BUCKET`、`ITEM_WEIGHTS`、`AGE_GROUPS`、`Sex`）。
6. `backend/app/domain/percentile.py`（`PercentileRow`、`lookup_p25`、`MIN_SAMPLE`；**注意 `:162-179` 那段「调用方职责」docstring**）。
7. `backend/tests/seed/test_trend_oracle.py` —— **Task 6 那份 test-only oracle**。你的 `classify_trend` 必须与它给出同样的分类，`test_trend_label_of_generated_data_is_truth` 就是把两者对齐的那条测试。
8. `backend/tests/architecture/test_domain_purity.py` —— 你要新建的 `app/domain/derive.py` 会被这 3 个 AST 守卫扫描（禁止 I/O、禁止 `import random`、禁止时钟调用）。

---

## 2. 预检已经替你排掉的 7 个坑（不要把它们又踩回去）

**① 判定表的行序是「波动大 → 持续下滑 → 稳步提升 → 稳定」（Ruling 64a，承重）。**
原 spec 把「持续下滑」印在第一行，那样「波动大」**可证明不可达**：6 项里 `min(#{d>0}, #{d<0}) ≥ 3` 等价于恰好 3 正 3 负，而这必然满足原「持续下滑」的第二分支「≥3 项为负变化」，于是每个波动大的学生都先被持续下滑吃掉。计划 Step 1 的 `test_volatile_outranks_declining` 是这条行序的**唯一守卫**（控制者实跑确认：3 项各降 12 + 3 项各升 10 → 必须是 `VOLATILE`；行序写反会得到 `DECLINING`）。

**② 「持续下滑」的第二分支是「≥3 项单项下降 ≥ `SINGLE_ITEM_DROP`(5) 分」，不是「≥3 项为负变化」（Ruling 64b）。**
原措辞下「稳定」类几乎无法存在：一个总分不变的学生只要六项里出现 3 个 −1 分的正常抖动就会被判持续下滑。

**③ 总分口径是国标加权总分 0–100，且必须「先各自整除、再相减」（Ruling 63/71/76）。**
`national_total(s) = Σ ITEM_WEIGHTS[i]·s[i] // 100`，`Delta = national_total(curr) − national_total(prev)`。**不是** `Σ w_i·delta_i / 100`（连续量，相差最多 1 分）。控制者已实跑构造出一个**恰好在阈值上分岔**的用例（`test_national_total_floor_makes_order_of_operations_matter`）：`Σprev = 7500 → 75`、`Σcurr = 7020 → 70`，整数口径 `Delta = −5`（触发）、连续口径 `−4.80`（不触发）。**这条测试的期望值是实跑出来的，不是算出来的**——如果你的实现给出别的数，先怀疑实现，不要改测试。
另：`national_total` 对「7 项任一为 `None`」与「键根本不存在」**同等对待**，一律返回 `None`（不做权重重归一）。

**④ `age_group` 是年级组名，不是 `"18-19"`（Ruling 85，这个坑已经出现两次）。**
计划 Step 1 的测试已全部改用 `LOWER_GRADE = AGE_GROUPS[0]`。`"18-19"` 在真表里是不存在的键。

**⑤ `WeaknessResult` 没有 `patterns` 字段（Ruling 98）。** 原计划列了它却从未定义语义、也没有消费者，已删。不要自己加回来。

**⑥ `W = 0` 时「相对最弱桶」= 桶内有效项得分均值最低者（Ruling 100）。**
并列时 → 该桶内最低单项得分更低者 → 仍并列按 `ITEM_BUCKET` 声明序（`endurance` → `strength` → `speed_flexibility`）。计划里 `test_no_weakness_dominant_tiebreak_then_declaration_order` 就是两级全并列的情形，**唯一答案是 `"endurance"`，断言必须是等号**（`assert x in (A, B)` 是两可断言，Ruling 8 明令禁止）。

**⑦ `derive` 的 `curr_scores` / `prev_scores` 必须含全部 7 项（含 BMI），缺键 `KeyError`（Ruling 101）。**
否则 `national_total` 会**静默返回 `None`**，同层内排序（spec §6.1 空洞一）在整个数据集上失效且不报错。另加一致性校验：`curr_total is not None` 与「7 项都非 None」必须同真同假，不一致 `ValueError`。

---

## 3. 要做的

严格按计划 **Task 8 Step 1 → 5** 走，TDD 红-绿：

- **Step 1**：把计划里那 **34 条**测试落进 `backend/tests/domain/test_derive.py`。四条注意：
  - `test_trend_label_of_generated_data_is_truth` 在计划里是 `...` 占位，**必须真正实现**，且遵守它的两条硬约束（**Ruling 75**）：**必须用零注入配置** `SeedConfig(dirty={"missing":0,"outlier":0,"unit_error":0,"duplicate":0})`，且**只对 `week1` 断言**。理由写在计划注释里（缺省注入下 4% missing 会让 `national_total` 返回 `None` → 走 INSUFFICIENT，0.5% outlier 凭空造大 delta，1% duplicate 让配对出现两行，**红的理由与趋势模型完全无关**；week8/week16 实测各有 5.0% / 4.2% 的人与 `trend_label` 不一致，那是刻意设计，`trend_label` 的权威时点就是学年起点）。
    **这条测试是 Task 6 的 test-only oracle 与你的生产实现之间唯一的对账点**，500 人必须逐人相等。若不相等，**先怀疑你的行序或口径**，不要改测试、也不要改 Task 6。
  - `test_smi_is_not_an_input_at_all` 用 `inspect.signature` 钉住签名本身（原计划那条 `test_smi_does_not_affect_flag` 是空转测试，已废）。
  - **空体测试恒绿、等于没有测试**：计划里所有 `...` 占位都必须实现。
  - 不要 `import numpy`，除非某条测试真的用到（Task 7 刚删掉一个死导入）。
- **Step 2**：跑出 `ModuleNotFoundError: app.domain.derive`。
- **Step 3**：实现 `derive.py`。除计划正文外注意：
  - `Trend` 的枚举值必须与 Task 6 写进 `trend_label` 的中文字面量**逐字相同**（`"持续下滑"` / `"波动大"` / `"稳步提升"` / `"稳定"` / `"insufficient_data"`），否则对账测试无法直接比较。
  - 阈值常量按 Interfaces 块声明，名字逐字照用（`TOTAL_DROP_THRESHOLD` / `DECLINING_ITEMS_THRESHOLD` / `SINGLE_ITEM_DROP` / `VOLATILE_MIN_SPLIT` / `VOLATILE_ITEM_SWING` / `IMPROVE_TOTAL_THRESHOLD` / `IMPROVE_SINGLE_ITEM_DROP_LIMIT` / `BODY_FAT_LIMIT`）。
  - `annual_change` 按 Ruling 99：7 个键（6 项 `.value` + `"national_total"`），值是年均量；**无历史时是 `{}`，不是 7 个 0.0**。
  - `flag_body_comp` 按 Ruling 97：`reasons` 是固定顺序的英文 token、`limit` 一律按性别填、两输入都缺时 `abnormal=False` 且 **docstring 必须写明「W≥2 且无 InBody 数据 → 落 Y3 而非 R1，即缺数据导致干预不足」**。
  - `app/domain/derive.py` 不得有任何 I/O、不得 import `app.refdata`、不得碰时钟（AST 守卫会拦）。`table` 相关的东西一律由调用方注入——本模块其实**不需要评分表**（它吃的是已算好的得分），若你发现需要，先上报。
- **Step 4**：`pytest tests/domain/test_derive.py -v` → **34 passed**；再 `pytest -q` 全量 → **362 passed**（328 + 34），`-W error` 同样全绿。
- **Step 5**：一个 commit。

### 变异验证（本项目立下的标准做法，必做）
至少四次，每次**必须完全还原并复核**（`git diff --stat` 为空、变异标记 `Select-String` 0 命中、还原后重跑全量）：
1. **行序反转**（持续下滑 放到 波动大 之前）→ `test_volatile_outranks_declining` 应变红。
2. **`<` 改 `<=`**（短板判定的 P25 比较符）→ `test_score_exactly_equal_to_p25_is_not_a_weakness` 应变红。
3. **`national_total` 改成连续量**（`/ 100` 而非 `// 100`，或先减后除）→ `test_national_total_floor_makes_order_of_operations_matter` 应变红。
4. **缺失项当 0 分**（Review Focus #2 的核心）→ `test_missing_item_not_counted_as_zero` 应变红。

**如果某次变异没有让任何测试变红，那说明对应的守卫是空转的——这是本轮最重要的发现类型，必须上报。**（Task 6 就靠变异测试查出过一条控制者以为成立、实际不成立的理由。）

---

## 4. 明确不要做的事

- 不实现 Task 9 的任何东西（`stratify` / `explain` / `Layer` / 黄金用例）。`DerivedResult` 是交给它的接口，本轮只产出它。
- 不改 `app/domain/indicators.py`、`app/domain/percentile.py`（Task 7 刚结案）。
- 不碰 `backend/app/seed/`、`backend/app/pipeline/`、`backend/app/db/`、`backend/app/adapters/`。
- 不新增数据文件。
- 不做物化/落库（Task 10）。
- 不放宽任何既有断言。基线 **328 passed**，本轮结束时既有 328 条必须仍全绿且断言未改。
- 不做本简报未要求的重构、注释补全、类型标注、额外抽象。
- 不新增计划未列的导出符号（`Trend` / `national_total` / `WeaknessResult` / `BodyCompFlag` / `DerivedResult` / `classify_trend` / `find_weaknesses` / `flag_body_comp` / `derive` / 8 个阈值常量，就这些）。

---

## 5. 交付

1. 一个 commit，message 形如：
   `feat: 派生指标 — 趋势四分类、短板与主导桶、体成分异常，总分口径统一为国标加权`
2. 新建报告 `.superpowers/sdd/2026-09-28-实施计划01-数据基座与分层引擎/task-8-report.md`，含：
   - 状态（DONE / DONE_WITH_CONCERNS / BLOCKED）与 commit 哈希；
   - 测试数（**328 → 362**）、`-W error` 结果、耗时；
   - Step 2 的 RED 输出与 Step 4 的 GREEN 输出；
   - **`test_trend_label_of_generated_data_is_truth` 的 500 人逐人对账结果**（一致数必须是 500/500；若不是，列出前 5 个不一致的 `student_id` + 期望 vs 实际 + 该生的六项 delta 与两个总分）；
   - **四次变异验证的结果**（每次红了几条、哪几条、失败消息要点）与还原证据；
   - `git diff --stat 23f3468..HEAD` 的输出（应只有 `derive.py` 与 `test_derive.py`），以及 `git diff --stat 23f3468..HEAD -- backend/app/seed/` 为空的证明；
   - AST 纯净性守卫结果（`pytest tests/architecture -v`）；
   - `annual_change` 与 `reasons` 的实际键/token 清单（供 Task 9 直接引用）；
   - **关切章节**（每条附可复现方法，并说明读的是生产状态还是重新推导）；
   - **前向约束章节**：至少写明 Task 9 消费 `DerivedResult` 时需要注意的事（`valid_count < 4` 的闸门、`dominant_bucket` 在 `W=0` 时的口径、`annual_change` 为 `{}` 表示无历史、`body_comp.limit` 一律非 None、`reasons` 的 token vocabulary），以及 Task 10 调用 `derive` 时必须自己先用 `national_total` 算好两个总分。
3. 报告写完后 shell 复核文件存在且非空（`(Get-Item <report>).Length`），末尾附 `git log --oneline -1` 与 `git status --short`（应为空）。
4. 临时探针全部删除，逐个 `Test-Path` 复核 False。

## 6. 最终返回给我什么

一段简明总结：状态、commit 哈希、测试数变化（328 → ?）、`-W error` 是否洁净、**500 人对账的一致数**、四次变异验证各红了几条与哪几条、`git diff --stat` 与 `app/seed/` 为空的证明、AST 守卫结果、`annual_change` 键清单与 `reasons` token 清单、**你上报的每一条关切（原文摘要 + 可复现方法）**、以及 `git status --short` 的输出。
