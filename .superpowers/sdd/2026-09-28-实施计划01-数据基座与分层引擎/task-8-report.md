# Task 8 实现者报告 — 派生指标（趋势 / 短板 / 体成分异常）

分支：`feature/plan-01-data-foundation`
基线 commit：`23f3468`（工作树干净，全程未 rebase / reset / 切分支 / force push）
本轮 commit：**`2a51aad`**（唯一一次提交）

---

## 1. 状态

**DONE_WITH_CONCERNS**

代码与测试全部按计划落地、全绿、四次变异验证全部命中。**9 条关切**，其中 **1 条是计划的承重缺陷**（关切 1：`derive` 的签名里没有 `age_group`，而它必须调 `find_weaknesses(curr, snapshot, sex, age_group)`；且 34 条测试对 `DerivedResult.weakness` **零覆盖**，这个缺口在测试上抓不到）。其余 8 条是计划未定义的口径（我已按最小发明原则处置并逐条写明理由）、计划文本的转写缺陷、以及两条实测发现。

**没有改动任何既有文件**：`git diff --stat 23f3468..HEAD` 只有新增的两个文件（§6）。Task 6 的三个 CSV 哈希未受影响。

---

## 2. 测试数、`-W error`、耗时

| 项 | 值 |
|---|---|
| 基线（`23f3468`，实现前实测） | **328 passed in 10.17s** |
| 本轮结束（`pytest -q`，全量） | **362 passed in 10.14s** |
| 本轮结束（`pytest -q -W error`，全量） | **362 passed in 10.41s**（洁净，0 warning） |
| 新文件 `tests/domain/test_derive.py` 单跑 | **34 passed in 0.72s** |
| 四次变异还原后的复跑（末次） | `pytest -q` **362 passed in 10.12s**；`-W error` **362 passed in 10.09s** |

328 → **362**（+34），与计划 Step 4 的期望数逐字一致（趋势 10 + 短板 9 + 体成分 7 + 国标总分 3 + derive 编排 5）。

`def test_` 实数复核（双路，Ruling 94）：
- `Select-String -Path tests\domain\test_derive.py -Pattern '^def test_'` → **34**
- `python -c` 读字节 + `re.findall(r'(?m)^def (test_\w+)')` → **34**，重名 **0** 个，文件 **22701** 字节

既有 328 条**一条未改、一条未放宽**（`git diff --stat 23f3468..HEAD` 里没有任何既有文件，见 §6）。

---

## 3. Step 2 的 RED 输出（逐字）

```
============================= test session starts =============================
platform win32 -- Python 3.11.1, pytest-9.1.1, pluggy-1.6.0 -- C:\Python\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\whwenhao\Desktop\Physical_Education_ims\backend
configfile: pyproject.toml
plugins: anyio-4.15.1, cov-7.1.0
collecting ... collected 0 items / 1 error

=================================== ERRORS ====================================
________________ ERROR collecting tests/domain/test_derive.py _________________
ImportError while importing test module 'C:\Users\whwenhao\Desktop\Physical_Education_ims\backend\tests\domain\test_derive.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Python\Lib\importlib\__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\domain\test_derive.py:11: in <module>
    from app.domain.derive import (
E   ModuleNotFoundError: No module named 'app.domain.derive'
=========================== short test summary info ===========================
ERROR tests/domain/test_derive.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.20s ===============================
```

失败原因正是计划 Step 2 要求的 `ModuleNotFoundError: app.domain.derive`，且是在测试文件第 11 行（`from app.domain.derive import (...)`）——即**测试先落盘、实现在后**，不是反过来。

（`Hint:` 一行的 `namess.` 是 pytest 9.1.1 的原文，不是转写笔误；本轮用同版 pytest 对一个同样「导入不存在模块」的临时文件复跑过一次采集，Hint 行逐字相同，临时文件已删除、`Test-Path` → `False`，见 §11。）

---

## 4. Step 4 的 GREEN 输出（`pytest tests/domain/test_derive.py -v`，逐字）

```
============================= test session starts =============================
platform win32 -- Python 3.11.1, pytest-9.1.1, pluggy-1.6.0 -- C:\Python\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\whwenhao\Desktop\Physical_Education_ims\backend
configfile: pyproject.toml
plugins: anyio-4.15.1, cov-7.1.0
collecting ... collected 34 items

tests/domain/test_derive.py::test_trend_declining_by_total_drop_only PASSED [  2%]
tests/domain/test_derive.py::test_trend_declining_by_three_items_dropping_five PASSED [  5%]
tests/domain/test_derive.py::test_two_items_dropping_five_below_total_threshold_is_stable PASSED [  8%]
tests/domain/test_derive.py::test_trend_volatile PASSED                  [ 11%]
tests/domain/test_derive.py::test_volatile_outranks_declining PASSED     [ 14%]
tests/domain/test_derive.py::test_one_zero_delta_makes_volatile_unreachable PASSED [ 17%]
tests/domain/test_derive.py::test_trend_improving PASSED                 [ 20%]
tests/domain/test_derive.py::test_trend_stable PASSED                    [ 23%]
tests/domain/test_derive.py::test_trend_insufficient_without_history PASSED [ 26%]
tests/domain/test_derive.py::test_trend_label_of_generated_data_is_truth PASSED [ 29%]
tests/domain/test_derive.py::test_weakness_below_p25_counted PASSED      [ 32%]
tests/domain/test_derive.py::test_score_exactly_equal_to_p25_is_not_a_weakness PASSED [ 35%]
tests/domain/test_derive.py::test_item_without_a_snapshot_row_is_not_a_weakness_and_not_counted PASSED [ 38%]
tests/domain/test_derive.py::test_bmi_never_counted_as_weakness PASSED   [ 41%]
tests/domain/test_derive.py::test_missing_item_not_counted_as_zero PASSED [ 44%]
tests/domain/test_derive.py::test_dominant_bucket_by_count_then_lowest_score PASSED [ 47%]
tests/domain/test_derive.py::test_dominant_bucket_tiebreak_by_lowest_score PASSED [ 50%]
tests/domain/test_derive.py::test_no_weakness_dominant_is_relative_weakest PASSED [ 52%]
tests/domain/test_derive.py::test_no_weakness_dominant_tiebreak_then_declaration_order PASSED [ 55%]
tests/domain/test_derive.py::test_body_fat_male_boundary PASSED          [ 58%]
tests/domain/test_derive.py::test_body_fat_female_boundary PASSED        [ 61%]
tests/domain/test_derive.py::test_muscle_below_p20_is_abnormal PASSED    [ 64%]
tests/domain/test_derive.py::test_muscle_exactly_at_p20_is_not_abnormal PASSED [ 67%]
tests/domain/test_derive.py::test_smi_is_not_an_input_at_all PASSED      [ 70%]
tests/domain/test_derive.py::test_missing_body_comp_is_not_abnormal_but_carries_the_limit PASSED [ 73%]
tests/domain/test_derive.py::test_flag_carries_value_and_limit_for_explain PASSED [ 76%]
tests/domain/test_derive.py::test_national_total_is_weighted_and_floored PASSED [ 79%]
tests/domain/test_derive.py::test_national_total_floor_makes_order_of_operations_matter PASSED [ 82%]
tests/domain/test_derive.py::test_national_total_returns_none_when_any_of_the_seven_is_missing PASSED [ 85%]
tests/domain/test_derive.py::test_derive_requires_all_seven_score_keys PASSED [ 88%]
tests/domain/test_derive.py::test_derive_annual_change_is_empty_without_history PASSED [ 91%]
tests/domain/test_derive.py::test_derive_annual_change_covers_six_items_plus_total PASSED [ 94%]
tests/domain/test_derive.py::test_derive_years_scales_the_annual_change PASSED [ 97%]
tests/domain/test_derive.py::test_derive_rejects_inconsistent_total_and_scores PASSED [100%]

============================= 34 passed in 0.72s ==============================
```

全量 GREEN：

```
........................................................................ [ 39%]
........................................................................ [ 59%]
........................................................................ [ 79%]
........................................................................ [ 99%]
..                                                                       [100%]
362 passed in 10.14s
```

**34 条测试的期望值一条未改**：全部按计划的字面断言落地（含 `test_national_total_floor_makes_order_of_operations_matter` 的 `75 / 70 / -5`、`test_no_weakness_dominant_tiebreak_then_declaration_order` 的等号断言 `"endurance"`）。控制者 Ruling 95/96 实跑过的期望值与生产实现**逐条吻合，第一次就跑绿**，没有出现「实现给出别的数」的情形。

---

## 5. `test_trend_label_of_generated_data_is_truth` — 500 人逐人对账

### 5.1 结果：**500 / 500 一致，不一致 0 人**

测试自身的两条断言（`agree == 500` 与 `mismatches == []`）在 Step 4 的 GREEN 里通过。为把明细取出来供本报告引用，另跑了一次独立探针（`_probe_task8.py`，**已删除**，`Test-Path` → `False`，见 §11），它调用的是**同一批生产函数**（`score_item` / `national_total` / `classify_trend`），不是另写一套：

```
dirty_marks: 0
years: ['2024-2025', '2025-2026']
pairs: 500 500 same set: True
agree: 500 / 500
mismatches: 0 []
label dist: {'持续下滑': 100, '波动大': 75, '稳定': 200, '稳步提升': 125}
score_* column cells differing from re-scored: 0
None totals: 0
```

### 5.2 这份测量读的是什么

**读的是生产代码的输出，不是我重新推导的输入**（硬规矩 #6）。链路逐段说明：

| 环节 | 来源 | 是否生产代码 |
|---|---|---|
| 原始测量值 | `build_dataset(SeedConfig(dirty={missing:0,outlier:0,unit_error:0,duplicate:0}))["fitness"]` 的记录字段（`height_cm` / `weight_kg` / `vital_capacity_ml` / `sprint_50m_s` / `sit_and_reach_cm` / `standing_jump_cm` / `strength_count` / `distance_run_s`） | Task 6 生产生成器 |
| 列名映射 | `app.seed.fitness.COLUMN_BY_ITEM` | Task 6 生产常量 |
| 单项得分 | `app.domain.indicators.score_item(standard(), item, raw, sex, age_group)` | Task 2 生产正查 |
| 龄组 | `age_group_of(age)` / `age_group_of(age - 1)`，按 `SEMESTERS` 的 `is_current` 认学年 | Task 2 生产函数 + Task 6 生产配置（Ruling 56） |
| 总分 | `app.domain.derive.national_total` | **本轮生产实现** |
| 分类 | `app.domain.derive.classify_trend` | **本轮生产实现** |
| 真值 | 记录里的 `trend_label` 字段 | Task 6 生产生成器 |

**刻意不读** 记录里的 `score_*` 诊断列——那是 Task 6 oracle（`tests/seed/test_trend_oracle.py`）的读法，生产侧再读一遍就退化成自证。作为交叉验证，探针额外比对了「重新正查出的 7 项得分」与「记录里的 `score_*` 诊断列」：**500 人 × 7 项 = 3500 个格子，差异 0 个**。这说明两条路径（生成期的中间量 vs 从原始值重新正查）逐格自洽，`_rescore` 的 BMI 算式（含 `round(..., 1)`）与 `_anthropometrics` 一致。

### 5.3 遵守的两条硬约束（Ruling 75）

1. **零注入配置**：`SeedConfig(dirty={"missing": 0, "outlier": 0, "unit_error": 0, "duplicate": 0})`。测试里另加一条自证断言 `assert ds["dirty_marks"] == []`（探针实测 `dirty_marks: 0`），把「配置真的生效了」这件事本身钉住——否则一旦 `SeedConfig` 的字段名改动导致注入配置被忽略，这条对账测试会静默退化成一个只反映脏数据比例的噪声源。
2. **只对 `week1` 断言**：`week1 = [r for r in ds["fitness"] if r["timepoint"] == "week1"]`，week8 / week16 一行都不进对账。上学年 / 本学年按 `SEMESTERS` 的 `is_current` 认（`{plan.academic_year: plan.is_current for plan in SEMESTERS}`），不按 `academic_year` 的字典序猜；测试里另有 `len(years) == 2` 与 `len(previous) == len(current) == 500` 与 `set(previous) == set(current)` 三道守卫。

### 5.4 标签分布与配额逐格吻合

实测 `{'持续下滑': 100, '波动大': 75, '稳定': 200, '稳步提升': 125}`，与 Task 6 `allocate_quota(SeedConfig().trend_mix, 500)` 的配额（`test_trend_oracle.py:518` 钉住的 `{"持续下滑": 100, "波动大": 75, "稳步提升": 125, "稳定": 200}`）**逐项相等**。

`None totals: 0` —— 零注入下 500 人 × 2 学年共 1000 条 week1 记录，`national_total` 一次都没有返回 `None`，故本轮对账**没有**走过 `INSUFFICIENT` 分支（这正是 Ruling 75 第 1 条要防的：缺省注入下 4% missing 会让一部分人从趋势模型掉进 `INSUFFICIENT`，红的理由与趋势无关）。

### 5.5 地板效应（Task 6 移交的前向约束）已容忍

Task 6 的 28 名被标记男生 `pull_up_or_sit_up` 两学年得分恒为 10、该项趋势恒为 0（`progress.md:643` / `:677`）。本轮对账覆盖全部 500 人、含这 28 人，**500/500 一致**，说明 `classify_trend` 对「某项 delta 恒为 0」的处理与生成器一致：`d == 0` 既不计正也不计负（spec §14 #23），使这批人更难被判「波动大」，但不影响他们落到其余三类。**未把「某项趋势为 0」当作「稳定」的正向证据**——`STABLE` 只是四分支皆不命中时的残差，代码里没有任何一处以「delta 全为 0」为判据。

---

## 6. `git diff --stat` 与 `app/seed/` 为空的证明

```
$ git diff --stat 23f3468..HEAD
 backend/app/domain/derive.py        | 497 ++++++++++++++++++++++++++++++++++++
 backend/tests/domain/test_derive.py | 417 ++++++++++++++++++++++++++++++
 2 files changed, 914 insertions(+)

$ git diff --stat 23f3468..HEAD -- backend/app/seed/
（无输出 = 空）
```

**只有两个新增文件，0 处修改、0 处删除**（`914 insertions(+)`、无 `deletions`），故 Task 1–7 的任何一行既有代码与任何一条既有断言都未被触碰。`backend/app/seed/` 的 diff 为空 ⇒ Task 6 的三个 CSV 哈希（`498AA3256678B01A` / `1234025C05843B27` / `835A98FCC0779B51`）不可能失效。

commit 内容复核（`git status --short` 在 `git add` 之后、`git commit` 之前）：

```
A  backend/app/domain/derive.py
A  backend/tests/domain/test_derive.py
?? backend/_commitmsg_task8.txt          ← commit -F 用的临时消息文件，提交后已删（Test-Path → False）
```

暂存区**恰好两个文件**，与简报 §5.1 的要求一致。

其他红线复核：

| 检查 | 命令 | 结果 |
|---|---|---|
| `backend/pe.db` 不存在 | `Test-Path backend\pe.db` | **False** |
| `backend/data/seed/` 为空 | `(Get-ChildItem backend\data\seed -Force \| Measure-Object).Count` | **0**（目录存在，`Test-Path` → True，文件数 0） |
| 工作树干净 | `git status --short` | **空** |
| 分支未变 | `git branch --show-current` | `feature/plan-01-data-foundation` |
| commit 数 | `git log --oneline 23f3468..HEAD` | **1** 条（`2a51aad`） |

commit message（无 BOM UTF-8 临时文件 + `git commit -F`，PowerShell 无 heredoc）：

```
feat: 派生指标 — 趋势四分类、短板与主导桶、体成分异常，总分口径统一为国标加权
```

中文在 `git log --oneline -1` 里逐字正确显示（无乱码），已复核。

---

## 7. AST 纯净性守卫结果（`pytest tests/architecture -v`）

```
platform win32 -- Python 3.11.1, pytest-9.1.1, pluggy-1.6.0 -- C:\Python\python.exe
rootdir: C:\Users\whwenhao\Desktop\Physical_Education_ims\backend
configfile: pyproject.toml
collected 3 items

tests/architecture/test_domain_purity.py::test_domain_has_no_forbidden_imports PASSED [ 33%]
tests/architecture/test_domain_purity.py::test_domain_has_no_clock_or_file_access PASSED [ 66%]
tests/architecture/test_domain_purity.py::test_domain_has_no_filesystem_access PASSED [100%]

============================== 3 passed in 0.03s ==============================
```

三个守卫都带 `assert DOMAIN.is_dir()` 空转防护（Ruling 89 / Task 1 关切 2 的产物），且 `app/domain/derive.py` 确实在被扫的目录里（`DOMAIN.rglob("*.py")`），故这 3 条**不是空转全绿**。

`derive.py` 的合规事实（逐条对守卫的封禁清单）：

- **import 只有三处**：`dataclasses.dataclass`、`enum.Enum`、`app.domain.indicators` / `app.domain.percentile`。封禁集 `{sqlalchemy, fastapi, requests, httpx, pydantic_settings, random}` **一个都没有**。
- **没有 import `app.refdata`**，也没有 import `app.db` / `app.pipeline` / `app.adapters` / `app.seed`。本模块**不需要评分表**：它吃的是已经正查成 0–100 的得分，方向问题在 `indicators` 那一层就抹平了（这一点已写进模块 docstring，避免下游误以为要注入 `table`）。
- **封禁的时钟调用**（`datetime.now` / `datetime.today` / `datetime.utcnow` / `date.today` / `time.time`）**一个都没有**；`years` 由调用方注入。
- **封禁的 I/O token**（`read_csv` / `.read_text` / `Path(` / `import os` / `__file__` / `json.load` / `pickle.load` 等 15 个）**一个都没有**；`\bopen\s*\(` 正则 0 命中。
- **不用随机数**：全模块无 `random` / `numpy` 采样调用（连 `numpy` 都没 import）。

---

## 8. `annual_change` 键清单 与 `reasons` token 清单（供 Task 9 直接引用）

以下全部由探针**实跑生产代码**取出（探针已删除，见 §11），不是从源码抄的。

### 8.1 `DerivedResult.annual_change` — 恰好 7 个键

dict 的**插入顺序**（Task 9 若要按序渲染文案，可直接依赖）：

```
['vital_capacity', 'sprint_50m', 'sit_and_reach', 'standing_jump',
 'pull_up_or_sit_up', 'distance_run', 'national_total']
```

即 `WEAKNESS_ITEMS` 的声明序（= spec §4.2 权重表的行序去掉 BMI）+ `"national_total"` 收尾。**`"national_total"` 是字面量字符串**，本模块没有为它设常量（简报 §4 明令不得新增计划未列的导出符号），Task 9 引用时请写字面量或自己起常量。

实测一例（prev 七项全 70、curr 七项全 80、`years = 1.0`）：7 个值全为 `10.0`；`years = 2.0` 时 `annual_change["national_total"] == 5.0`。

**`{}`（空 dict）的两种含义**，Task 9 必须都当成「无从比较」而不是「变化为 0」：
1. `prev_scores is None` —— 无历史体测（如新生），Ruling 99 明定；
2. 总分不可比（`curr_total` 或 `prev_total` 为 `None`，通常是七项里有缺测）—— 计划未定义，见**关切 3**。

### 8.2 `BodyCompFlag.reasons` — token vocabulary 恰好 2 个

```
('body_fat_high', 'muscle_low')
```

探针把 `body_fat_pct ∈ {None, 15.0, 20.0, 20.1, 29.0} × muscle_mass_kg ∈ {None, 39.9, 40.0, 50.0} × sex ∈ {MALE, FEMALE} × snapshot_muscle_p20 ∈ {None, 40.0}`（共 80 个组合）全跑了一遍，**观察到的 token 集合只有这两个**，无第三个。顺序固定为**先体脂率后肌肉量**（`flag_body_comp(29.0, 39.9, Sex.FEMALE, 40.0).reasons == ('body_fat_high', 'muscle_low')` 实测成立），`explain()` 可直接按序渲染。

`abnormal == bool(reasons)` 恒成立，故 `abnormal is True/False` 是真 `bool`（测试里用的是 `is`，不是 `==`）。`reasons == ()` ⇔ `abnormal is False`。

### 8.3 `BodyCompFlag.limit` — 一律非 None

实测 `flag_body_comp(None, None, Sex.MALE, None).limit == 20.0`、`flag_body_comp(None, None, Sex.FEMALE, None).limit == 28.0`：即使 `body_fat_pct is None`、`snapshot_muscle_p20 is None`，`limit` 仍按性别填（Ruling 97②）。`BODY_FAT_LIMIT = {Sex.MALE: 20.0, Sex.FEMALE: 28.0}`。

### 8.4 其余导出符号与常量（实测清单）

`derive.py` 自己定义的公开符号**恰好是简报 §4 允许的那 17 个**，一个不多：

- 4 个数据类 / 枚举：`Trend`、`WeaknessResult`、`BodyCompFlag`、`DerivedResult`
- 5 个函数：`national_total`、`classify_trend`、`find_weaknesses`、`flag_body_comp`、`derive`
- 8 个阈值常量：`TOTAL_DROP_THRESHOLD = 5`、`DECLINING_ITEMS_THRESHOLD = 3`、`SINGLE_ITEM_DROP = 5`、`VOLATILE_MIN_SPLIT = 3`、`VOLATILE_ITEM_SWING = 10`、`IMPROVE_TOTAL_THRESHOLD = 5`、`IMPROVE_SINGLE_ITEM_DROP_LIMIT = 5`、`BODY_FAT_LIMIT = {Sex.MALE: 20.0, Sex.FEMALE: 28.0}`

（探针列出的另外 9 个「公开名」`Enum` / `dataclass` / `ITEM_BUCKET` / `ITEM_WEIGHTS` / `WEAKNESS_ITEMS` / `ScoredItem` / `Sex` / `PercentileRow` / `lookup_p25` 是 `import` 进来的既有符号，不是本轮新增。）

模块私有名 3 个：`_SEVEN_ITEMS`（= `tuple(ScoredItem)`）、`_BUCKET_ORDER`（从 `ITEM_BUCKET` 派生，实测序为 `endurance → strength → speed_flexibility`）、`_require_seven_keys` / `_scoped_age_group`（两个私有校验助手）。**没有 `WeaknessResult.patterns`**（Ruling 98）。

`Trend` 的五个值实测为 `"持续下滑"` / `"波动大"` / `"稳步提升"` / `"稳定"` / `"insufficient_data"`，与 Task 6 写进 `trend_label` 的中文字面量**逐字相同**——§5 的 500/500 对账就是这个相等性的直接证据（`got.value == expected` 是字符串逐字比较）。`Trend` 是 `str` 枚举，故 `Trend.STABLE == "稳定"` 直接成立。

---

## 9. 四次变异验证

四次全部命中（**没有任何一次是空转**）。每次的做法一致：`SearchReplace` 改 `derive.py` → **双路复核字节真的落盘**（`Get-Item.Length` + `LastWriteTime` 变了、`Select-String` 命中 1、`python` 读字节数与 `MUTATION-n` 计数一致）→ 跑全量 → `git checkout -- backend/app/domain/derive.py` 还原 → **三重复核还原**（`git diff --stat` 为空、变异标记 `Select-String` 与 python 双路 0 命中、还原后重跑全量 362 passed）。

`derive.py` 的还原基线（首次 `git checkout` 之后固定不变）：**27564 字节 / SHA256 前 16 位 `97036CE5C35AE9ED`**。四次变异还原后逐次实测均为这两个值（见 §9.5 关于行尾的说明）。

### 9.1 变异 1 — 行序反转（持续下滑 放到 波动大 之前）→ **3 条红**

植入（`classify_trend` 内，带 `# MUTATION-1` 标记）：把 `Trend.DECLINING` 的整个 `if` 块搬到 `Trend.VOLATILE` 的 `if` 块之前。
落盘复核：`Length 27067 → 26935`、`LastWrite` 推进、`Select-String MUTATION-1` = 1、`python` 字节数 26935 / `MUTATION-1` 计数 1。

红了 **3** 条（`3 failed, 31 passed in 0.88s`）：

| 测试 | 失败消息要点 |
|---|---|
| `test_volatile_outranks_declining` ← **计划指定的守卫** | `assert <Trend.DECLINING: '持续下滑'> == <Trend.VOLATILE: '波动大'>`（`- 波动大 / + 持续下滑`） |
| `test_trend_volatile` | 同上，`DECLINING` != `VOLATILE` |
| `test_trend_label_of_generated_data_is_truth` | `AssertionError: 500 人逐人对账只一致 425 人（不一致 75 人）` / `assert 425 == 500` |

**不一致数恰好是 75**，等于 `allocate_quota` 给「波动大」的配额 ⇒ 行序写反时**全部 75 名波动大学生一个不漏地被持续下滑吃掉**，与 Ruling 64a「波动大可证明不可达」的推理**逐字吻合**。这是对那条 Ruling 的实测确认（读的是生产代码被变异后的实际 pytest 输出，不是推理）。详见**关切 6**。

还原复核：`git diff --stat` 空、`MUTATION` 标记 `Select-String` 0 / python 0、27564 字节 / `97036CE5C35AE9ED`、`git status --short` 空、`pytest -q` **362 passed in 10.20s**。

### 9.2 变异 2 — `<` 改 `<=`（短板判定的 P25 比较符）→ **1 条红**

植入：`if score < line:` → `if score <= line:  # MUTATION-2`。
落盘复核：`Length 27564 → 27579`、`Select-String MUTATION-2` = 1、python 字节 27579 / 计数 1。

红了 **1** 条（`1 failed, 361 passed in 10.38s`）：

| 测试 | 失败消息要点 |
|---|---|
| `test_score_exactly_equal_to_p25_is_not_a_weakness` ← **计划指定的守卫** | `AssertionError: assert (1 == 0)` / `where 1 = WeaknessResult(items=(<ScoredItem.DISTANCE_RUN: 'distance_run'>,), count=1, valid_count=6, dominant_bucket='endurance').count` |

失败消息把 spec §14 #21 描述的后果直接摆出来了：一个得分**恰等于** P25 的学生被判成短板（`count` 0→1），且 `dominant_bucket` 从「相对最弱桶」变成了 `endurance`（因为 `W` 从 0 变成 1，走的是另一条分支）——即比较符一字之差会**同时**改掉 `W`、`items`、`dominant_bucket` 三个下游量。

500 人对账测试**没有**变红（它不调 `find_weaknesses`），符合预期。

还原复核：`git diff --stat` 空、标记 0 命中（双路）、27564 / `97036CE5C35AE9ED`、`git status --short` 空、**362 passed in 10.09s**。

### 9.3 变异 3 — `national_total` 改成连续量（`/ 100` 而非 `// 100`）→ **1 条红**

植入：`... zip(_SEVEN_ITEMS, values)) // 100` → `... / 100  # MUTATION-3`。
落盘复核：`Length 27564 → 27577`、`Select-String MUTATION-3` = 1、python 字节 27577 / 计数 1。

红了 **1** 条（`1 failed, 361 passed in 10.47s`）：

| 测试 | 失败消息要点 |
|---|---|
| `test_national_total_floor_makes_order_of_operations_matter` ← **计划指定的守卫** | `AssertionError: assert (75.0 == 75 and 70.2 == 70)` / `where 75.0 = national_total({...全 75...})` / `and 70.2 = national_total({...SPRINT_50M: 60, DISTANCE_RUN: 66...})` |

**`70.2` 与 Ruling 96 实跑出的连续口径值逐字相同**（`7020 / 100 = 70.2`），即这条构造真的落在阈值两侧：整数口径 `70 − 75 = −5` 触发、连续口径 `−4.80` 不触发。注意 `75.0 == 75` 在 Python 里为真，所以第一个合取项没红——**红的是 `70.2 == 70`**，正是分岔所在的那一项。这条测试的构造是有效的。

**关键发现**：`test_trend_label_of_generated_data_is_truth` 在这次变异下**仍然全绿**（`1 failed, 361 passed`，唯一的 FAILED 是 floor 那条）。详见**关切 5**。

还原复核：`git diff --stat` 空、标记 0 命中（双路）、27564 / `97036CE5C35AE9ED`、`git status --short` 空、**362 passed in 10.30s**。

### 9.4 变异 4 — 缺失项当 0 分（Review Focus #2 的核心）→ **1 条红**

植入：把 `if score is None or line is None: continue` 拆成「只有无判定线才 `continue`」+ `if score is None: score = 0  # MUTATION-4`。
落盘复核：`Length 27564 → 27611`、`Select-String MUTATION-4` = 1、python 字节 27611 / 计数 1。

红了 **1** 条（`1 failed, 361 passed in 10.25s`）：

| 测试 | 失败消息要点 |
|---|---|
| `test_missing_item_not_counted_as_zero` ← **计划指定的守卫** | `AssertionError: assert (6 == 5)` / `where 6 = WeaknessResult(items=(<ScoredItem.VITAL_CAPACITY: 'vital_capacity'>,), count=1, valid_count=6, dominant_bucket='endurance').valid_count` |

失败消息把 Review Focus #2 要防的缺陷形态完整暴露了：一个**没测**的肺活量既让 `valid_count` 从 5 虚高到 6（分母被污染，可能让本该 `insufficient_data` 的学生通过 `< 4` 闸门），又凭空造出一条短板（`count` 0→1，`items` 里出现 `VITAL_CAPACITY`），还顺带把 `dominant_bucket` 从 `endurance` 之外的值改成了 `endurance`。三处同时错，全程不报错——正是本项目最怕的形态，而这条守卫拦得住。

还原复核：`git diff --stat` 空、`MUTATION` 标记 `Select-String` 0 / python 0、**27564 字节 / SHA256 `97036CE5C35AE9ED`**、`git status --short` 空、`pytest -q` **362 passed in 10.12s**、`pytest -q -W error` **362 passed in 10.09s**。

### 9.5 还原证据汇总与一条行尾注意事项

| 变异 | 红的条数 | 红的测试 | 还原后 `git diff --stat` | 还原后标记命中（Select-String / python） | 还原后字节 / SHA256[:16] | 还原后全量 |
|---|---|---|---|---|---|---|
| 1 行序反转 | **3** | `test_volatile_outranks_declining`、`test_trend_volatile`、`test_trend_label_of_generated_data_is_truth` | 空 | 0 / 0 | 27564 / `97036CE5C35AE9ED` | 362 passed |
| 2 `<`→`<=` | **1** | `test_score_exactly_equal_to_p25_is_not_a_weakness` | 空 | 0 / 0 | 27564 / `97036CE5C35AE9ED` | 362 passed |
| 3 `//`→`/` | **1** | `test_national_total_floor_makes_order_of_operations_matter` | 空 | 0 / 0 | 27564 / `97036CE5C35AE9ED` | 362 passed |
| 4 缺项当 0 分 | **1** | `test_missing_item_not_counted_as_zero` | 空 | 0 / 0 | 27564 / `97036CE5C35AE9ED` | 362 passed（`-W error` 亦 362） |

**四次全部命中，0 次空转**，且**四次红的都包含计划指定的那条守卫**（变异 1 额外多红 2 条）。

⚠️ **行尾注意事项（写入纪律，见关切 7）**：`derive.py` 首次写入时是 bare LF、**27067** 字节、SHA256[:16] `C77A991CA347C1E2`；第一次 `git checkout --` 还原后变成 CRLF、**27564** 字节、`97036CE5C35AE9ED`（差 497 = 该文件的行数，`core.autocrlf=true`）。**内容等价**（`git diff --stat` 全程为空即证），但 SHA256 跨 checkout 不可比。故本轮的还原判据以「`git diff --stat` 为空 + 变异标记双路 0 命中 + 还原后重跑全量 362」为准，SHA256 只用于同一次 checkout 之后的逐次比对（后三次还原的哈希逐次相同）。这也再次印证 Task 7 的延后 Minor：**终审前不要跑 `git add --renormalize`**，否则整文件 diff 会污染被当作落盘证据的 `--stat` / `--numstat`。

---

## 10. 关切

每条都附**可复现的测量方法**，并注明读的是**生产代码的（中间）状态**还是**我重新推导的输入**。

### 关切 1（**承重，计划缺陷**）— `derive` 的签名里没有 `age_group`，但它必须调 `find_weaknesses(curr, snapshot, sex, age_group)`；且 34 条测试对 `DerivedResult.weakness` 零覆盖

**矛盾在哪**（读的是计划文本本身，逐字对读即可复现）：
- 计划 `:1190` 定义 `find_weaknesses(curr, snapshot, sex, age_group) -> WeaknessResult` —— 第 4 个参数 `age_group: str` 是**必需**的，`lookup_p25(snapshot, item, sex, age_group)` 要用它精确匹配快照行。
- 计划 `:1196` 定义 `derive(curr_scores, prev_scores, curr_total, prev_total, years, body_fat_pct, muscle_mass_kg, sex, snapshot, snapshot_muscle_p20)` —— **10 个参数，没有 `age_group`**，同一段却写明「内部依次调用 `classify_trend`、`find_weaknesses`、`flag_body_comp`」。
- `DerivedResult`（`:1187`）的 6 个字段里也没有 `age_group`，故也无法从结果对象里回读。

即：`derive` 拿不到 `find_weaknesses` 必需的第 4 个实参。计划的 5 条 derive 测试全部用 10 个位置参数调用（`:1471` / `:1475` / `:1483` / `:1492` / `:1501`），逐字数过，确认不是我漏读。

**为什么它承重**：生产上 `snapshot` 是整张快照（2 性别 × 2 年级组 × 6 项 = **24 行**）。若 `derive` 随便挑一个年级组，另一个年级组的学生会**用错判定线**——Task 7 实测跨组 P25 差 `−7…+34` 分、均值 `+9.90`（`progress.md` / spec §14 #24），其中 `distance_run` 四组差 `+30/+34/+20/+20` 且权重 20%（全表最高）。这会静默改变 `W`、改变红黄绿比例，全程不报错。

**为什么 34 条测试抓不到它**：测试用的 `SNAP = [snap(i, 60) for i in ALL6]` 只有 `Sex.MALE` + `LOWER_GRADE` **一个组**，且 5 条 derive 测试**没有一条断言 `r.weakness`**（它们只断言 `trend` / `annual_change` / `national_total` / `sex`，以及两个异常）。所以无论 `derive` 怎么取 `age_group`，这 34 条都同样绿。

**我的处置**（最小发明，未改任何签名、未加任何参数、未新增导出符号）：新增私有函数 `_scoped_age_group(snapshot, sex)`，口径为「**调用方传入的 `snapshot` 已收窄到该生的 (性别, 年级组) 分组**」——与 `snapshot_muscle_p20` 由调用方预先查好再传进来是**同一套分工**（这是我选这个读法的主要理由：计划已经把「按组查百分位」这件事放在调用方了）。实现：

- 性别匹配的行携带**恰好 1 个**年级组 → 用它；
- 携带 **>1 个** → `ValueError` **响亮失败**，不静默挑一个；
- 携带 **0 个**（该组无快照行）→ 返回空串 `""`：它不可能等于任何真实年级组名（`AGE_GROUPS` 是 `"大一、大二"` / `"大三、大四"`），于是 `lookup_p25` 逐项返回 `None`，等价于「该组无判定线」→ `valid_count = 0` → 触发 Task 9 的 `< 4` 不分层闸门，正是应有的后果。

**测量方法（读的是生产代码的实际行为，不是我推导的输入）**：

```
$ python -c "…from app.domain.derive import derive, national_total, _scoped_age_group;
             …snap = compute_snapshot(两学年 × 6 项 × 40 人的 male 行, standard()); …"
full snapshot rows: 12
groups for male: ['大一、大二', '大三、大四']
ValueError raised OK -> derive 的 snapshot 必须已收窄到该生的 (性别, 年级组) 分组；性别 male 下出现了 2 个年级组 ['大一、大二', '大三、大四']，无法确定用哪一条判定线
scoped rows: 6 -> age_group resolved: '大一、大二'
empty snapshot -> age_group resolved: ''
```

三种情形（整张快照 / 预筛快照 / 空快照）都实测过，行为如上。

**请裁定**（三选一，我不自选）：
- **(A)** 给 `derive` 加第 11 个参数 `age_group: str`（与 `find_weaknesses` 对称、最直白；代价是计划的 5 条 derive 测试要改成 11 个实参，且 `DerivedResult` 或许也该带上它以便落库追溯）；
- **(B)** 认可我的「snapshot 必须预筛」口径，把它写进计划的接口契约与 Task 10 派单（**并且补 2 条测试**：一条钉「整张快照 → ValueError」，一条钉「预筛快照 → `weakness` 正确」，把这个目前的零覆盖缺口补上）；
- **(C)** 别的口径（例如让 `derive` 接受 `snapshot` 的同时接受 `PercentileRow` 已选好的 6 行）。

**若判断错的代价**：选 (B) 而将来某人给 `derive` 传整张快照 → 立刻 `ValueError`，不静默；选 (A) 而我这版留在库里 → Task 10 会撞上 `ValueError` 然后回来改签名，成本是一个任务的一次返工。**两种都不会静默产出错误的分层结果**，这是我选「响亮失败」而不是「静默挑一个」的原因。

---

### 关切 2 — `classify_trend` 在 `prev_total` / `curr_total` 为 `None` 时的行为，计划未定义

**矛盾在哪**：计划 `:1189` 只规定了「`prev` 为 `None` 直接返回 `INSUFFICIENT`」，没规定总分为 `None` 时怎么办。但 Ruling 101 的一致性校验（计划 `:1198`）**明确允许** `curr_total is None` 这一合法状态（它与「7 项里有 `None`」同真同假）。此时字面实现 `(curr_total - prev_total) / years` 会 `TypeError: unsupported operand type(s) for -: 'NoneType' and 'int'`。

**这不是边角**：它是 Review Focus #2（单项缺失）与 Task 6 的 4% missing 注入的**常态路径**。一个缺测学生走 `derive` 就会炸。

**我的处置**：`if prev is None or prev_total is None or curr_total is None: return Trend.INSUFFICIENT`。理由：总分不可得 = 无从比较 = 「不知道」，与「无历史体测」是同一类认识论状态；判成 `STABLE` 会让规则 Y4 对该生**静默失效**（Y4 是趋势的唯一消费者，`STABLE` 不触发升级），而 `INSUFFICIENT` 按 spec §6.3 表末行的语义本来就「不触发 Y4」，两者在 Y4 上后果相同，但 `INSUFFICIENT` 如实说出了「没算出来」。

**测量方法（读生产代码）**：`pytest tests/domain/test_derive.py -q` 全绿即证 `prev_total is None` 的那条路径被走到（`test_trend_insufficient_without_history` 与 `test_derive_annual_change_is_empty_without_history` 都传 `prev_total=None`）；`curr_total is None` 的那条路径**34 条测试里没有覆盖**（见关切 3 末尾的补测建议），我是靠 `python -c` 直接调 `classify_trend(base, base, 75, None, 1.0)` 确认它返回 `INSUFFICIENT` 而不是抛异常。

**请裁定**：接受 `INSUFFICIENT`，还是要求 `derive` 在 `curr_total is None` 时直接 `ValueError`（即「缺测学生不进派生」）？后者会与 spec §6.2 末行「`valid_count < 4` → `insufficient_data`，进异常名单」冲突（那批学生是**要**被派生、然后被闸门拦下的，不是要在派生阶段就炸掉），故我不建议。

---

### 关切 3 — `annual_change` 在「有历史但总分不可比」时的口径，计划未定义；我选了 `{}`，代价是丢掉 5 项可比信息

**矛盾在哪**：Ruling 99（计划 `:1188`）只规定了两种状态——「无历史 → `{}`」与「有历史 → 恰好 7 个键」。但缺测学生会落到第三种状态：`prev_scores` 存在（有历史）、`curr_total` 为 `None`（七项里有一项缺测）。此时：
- `"national_total"` 键算不出来（`None - prev_total`）；
- 6 个单项键里，缺测那一项也算不出来（`None - prev_scores[i]`），其余 5 项**是可比的**。

**我的处置**：一律归 `{}`（与「无历史」同一表示），**不填部分键、不填 0.0**。理由与 Ruling 99 同源：0.0 是「一年没变化」，与「无从比较」是两件事；而**半张表**（5 或 6 个键）会让 Task 9 的文案在缺项上要么说不出话、要么说出假话，且键数不定的 dict 迫使下游处处防御。

**代价（如实记录）**：一个只有 1 项缺测的学生会丢掉另外 5 项的年均变化量，`explain()` 因此渲染不出「你的肺活量年均提升 3 分」这类文案——尽管这个信息本来是有的。

**测量方法（读生产代码）**：探针实测 `derive(curr, None, ...)` → `no-history annual_change: {}`；「有历史但 `curr_total=None`」这条路径**34 条测试里没有覆盖**，我是靠读代码确认分支条件 `prev_scores is not None and curr_total is not None and prev_total is not None`。

**请裁定**：接受 `{}`，还是改为「只填可比的键」（键数 0–7 不定）？若改为后者，`test_derive_annual_change_covers_six_items_plus_total` 的 `set(r.annual_change) == …` 断言仍成立（它的数据全项齐备），但需要**新增**一条「缺测学生的 `annual_change` 键集」的测试来钉住口径，否则又是一个零覆盖的分支。

**附带一条同源的小缺口**：Ruling 101 的一致性校验只查 `curr`，不查 `prev`。若调用方传了完整的 `prev_scores` 却传 `prev_total=None`（自己算错了口径），`derive` 会**静默**产出 `trend=INSUFFICIENT` + `annual_change={}`，看起来像「无历史」，实际是调用方的 bug。我按 Ruling 101 的字面只校验了 `curr`（不擅自扩大校验范围）。建议：把同一条校验对称地加到 `prev_scores is not None` 的分支上（2 行），或明确写明「`prev` 侧不校验」是有意为之。

---

### 关切 4（计划文本转写缺陷，Minor）— 计划的导入行与 `total()` 助手用了两个不同的名字，逐字照抄会 `NameError`

**矛盾在哪**：计划 `:1213` 写 `from app.domain.indicators import AGE_GROUPS, WEAKNESS_ITEMS, ScoredItem as I, Sex`——只绑定了别名 `I`；但同一段 `:1236` 的 `total()` 助手函数体写的是 `return national_total({**scores6, ScoredItem.BMI: bmi})`，用的是**真名** `ScoredItem`。逐字照抄计划的话，`ScoredItem` 这个名字没有被绑定，第一次调用 `total()` 就会 `NameError: name 'ScoredItem' is not defined`——而 `total()` 被 9 条趋势测试里的 8 条调用，等于**整个趋势测试组全红**，且红的理由与趋势模型无关。

这与 Ruling 93（简报把体测去重键 `(student_no, batch_key)` 写成 `(student_no, tested_on)`）同类：**对既有/自身文本的事实性描述出错**，而实现者没有理由怀疑它。

**我的处置**：导入真名再起别名——`from app.domain.indicators import (AGE_GROUPS, WEAKNESS_ITEMS, ScoredItem, Sex, age_group_of, score_item)` 然后 `I = ScoredItem`。这样**两个名字都能用**，计划里 34 条测试的函数体（含 `total()` 的 `ScoredItem.BMI` 与所有 `I.XXX`）**逐字未改**。文件头留了一行注释说明这个偏差及其理由。

**测量方法**：静态可复现——把 `I = ScoredItem` 删掉、改回 `ScoredItem as I` 导入，跑 `pytest tests/domain/test_derive.py -q`，第一条调用 `total()` 的测试即 `NameError`。（我没有真的跑这个反向实验，因为 Step 2 的 RED 必须是 `ModuleNotFoundError`；这条是纯文本对读，两处行号已给。）

---

### 关切 5（实测发现，非缺陷，但值得记账）— 500 人对账测试**不守卫**整除口径，`//` 的唯一守卫是那一条构造测试

**发现**：变异 3（`national_total` 改 `/ 100`）下，全量结果是 `1 failed, 361 passed`，**唯一的 FAILED 是 `test_national_total_floor_makes_order_of_operations_matter`**——`test_trend_label_of_generated_data_is_truth` 仍然全绿（500/500 一致）。

**含义**：Ruling 76 说的「两种口径的差值在 500 人里有 443 人非零（区间 `[−0.90, +0.95]`）」在**总分数值**层面成立，但在 week1 的**分类结果**层面，这 443 人的差值一个都没有跨过 `±5` 的阈值。所以「整除 vs 连续」这条口径在 500 人数据集上对趋势标签**零影响**，对账测试对它**零覆盖**。

**这不是缺陷**：`test_national_total_floor_makes_order_of_operations_matter` 本来就是为这个而存在的构造测试（Ruling 96 的第一版构造测不出分岔、被实跑换掉，正说明控制者清楚这一点）。但值得记进账本：**若将来有人把 `//` 「简化」成 `/`，只有那一条会红；500 人对账给不出任何信号**，故不能用「对账测试还绿着」来论证总分口径没被动过。

**测量方法（读的是生产代码被变异后的实际 pytest 输出，不是推理）**：§9.3 的 `1 failed, 361 passed in 10.47s` 与它列出的唯一 FAILED 行。可复现：重做变异 3 后跑 `python -m pytest -q`，看 short test summary 里是否只有 floor 那一条。

---

### 关切 6（实测确认一条 Ruling，非缺陷）— 行序反转时不一致数**恰好 75**，等于「波动大」的配额

变异 1 下对账测试报 `500 人逐人对账只一致 425 人（不一致 75 人）`。`500 − 425 = 75`，而 `allocate_quota(SeedConfig().trend_mix, 500)` 给「波动大」的配额正是 **75**（`test_trend_oracle.py:518` 钉住）。即行序写反时，**全部 75 名波动大学生一个不漏地被持续下滑吃掉，其余 425 人一个都没被误伤**——与 Ruling 64a 的推理「每一个波动大的学生都会先被持续下滑吃掉，波动大永远命中不了」**逐字吻合，且是精确的（不是「大部分」）**。

顺带确认了一件事：`min(#{d>0}, #{d<0}) >= 3` 且 `max|d| >= 10` 的学生在生成数据里**必然**同时满足「≥3 项下降 ≥5 分」（否则不一致数会 < 75）。这是 Ruling 64a「可证明不可达」的实测侧面。

**测量方法（读的是生产代码被变异后的实际输出）**：§9.1 的失败消息 + §5.1 探针打出的 `label dist` 里的 `'波动大': 75`。可复现：重做变异 1 后跑 `pytest tests/domain/test_derive.py -q`，读 `agree` 的数值。

**建议**：把「75 = 波动大配额，精确相等」这条实测数字记进账本的 Ruling 64a 条目下，作为该 Ruling 的实测证据（此前它只有构造性证明）。

---

### 关切 7（写盘 / 环境纪律，非缺陷）— 本轮 0 次写盘事故；但 `git checkout` 会改行尾，SHA256 跨 checkout 不可比

本轮**没有触发**写盘事故（Task 7 那种「工具报成功、`Read` 读到新内容、磁盘上仍是旧版」的情形一次都没出现）：`test_derive.py` 首次 `Write` 落盘正常（22701 字节 / `LastWrite` 推进 / 34 个 `def test_`），`derive.py` 首次 `Write` 落盘正常（27067 字节），四次 `SearchReplace` 变异**全部**正常落盘（每次都有 `Length` 变化 + `LastWriteTime` 推进 + `Select-String` 与 python 双路命中 1 + pytest 真跑出了变异行为，四重证据）。这与 Task 7 的实测边界一致：**失效只发生在「对同一已存在文件的第二次及以后写入」**，而本轮四次 `SearchReplace` 都是对同一文件的第 2/3/4/5 次写入却都成功了——故那条边界**不是必然规律**，`SearchReplace` 本身是可靠的，Task 7 那次更像是偶发。**纪律不变**：每次编辑后仍以 shell 复核为准。

**但发现一条新的、会污染取证的事**：`git checkout -- backend/app/domain/derive.py` 还原之后，文件的行尾从我写入时的 bare LF 变成了 CRLF（`core.autocrlf=true`），字节数 `27067 → 27564`（差 **497**，恰等于 `git diff --stat` 报的该文件行数），SHA256 前 16 位 `C77A991CA347C1E2 → 97036CE5C35AE9ED`。**内容等价**（`git diff --stat` 全程为空即证，`git status --short` 亦空）。

后果与处置：**跨 checkout 的 SHA256 / `Length` 不可比**。本轮的还原判据因此一律以「`git diff --stat` 为空 + 变异标记双路 0 命中 + 还原后重跑全量 362 passed」三重为准，SHA256 只在首次 checkout 之后用于逐次比对（后三次均为 `97036CE5C35AE9ED`，逐次相同 ⇒ 四次还原都是**逐字节精确**的）。这条与 Task 7 的延后 Minor 同源，**再次印证：终审前不要跑 `git add --renormalize`**——否则整文件 diff 会把被当作落盘/范围证据的 `--stat` / `--numstat` 全部污染成噪音。

另记：`test_derive.py` 全程是 bare LF、未被 checkout 过，故其字节数（22701）自始至终可比。

**测量方法**：§9 各小节里的 `Length=` 与 `python bytes` 行、以及每次还原后的 `sha256[:16]`。全部可复现（`Get-Item`、`Get-FileHash`、`python -c "hashlib.sha256(...)"`）。

---

### 关切 8（**前向缺口，Task 10 会撞上**）— `snapshot_muscle_p20` 在仓内**没有生产者**

**矛盾在哪**：`flag_body_comp` 的第 4 个参数 `snapshot_muscle_p20`（spec §6.3② 的「肌肉量 < 同龄同性别 P20」）按计划应由调用方从百分位快照里查好再传入。但：

- `PercentileRow.item` 的类型是 `ScoredItem`（`percentile.py:57`），而 `ScoredItem` 只有 7 个成员，**全是国标计分项，没有肌肉量**；
- `compute_snapshot` 的契约第一行就是 `key = (Sex(row["sex"]), row["age_group"], ScoredItem(row["item"]))`（`percentile.py:203`），传 `"muscle_mass_kg"` 会直接炸；
- `percentile.py:31` 的注释明写「20 是体成分维度 C 的肌肉量判定线（spec §6.3②）」，即 P20 那一档**是为这个用途声明的**，但没有任何代码路径能产出一行肌肉量的快照。

**测量方法（读的是生产代码的实际行为）**：

```
$ python -c "…compute_snapshot([{'sex':'male','age_group':'大一、大二','item':'muscle_mass_kg','score':50}]*40, standard())…"
ValueError -> 'muscle_mass_kg' is not a valid ScoredItem
$ Select-String -Path backend\app\db\models.py -Pattern '_in_domain\("item"' | Measure-Object → Count
0
```

即：**domain 层拒绝**，而 **ORM 层不拒绝**（`PercentileSnapshot.item` 是 `String(32)`，`models.py:369` 注释写「取 ScoredItem 的值」，但 `__table_args__` 里只对 `source` 与 `sex` 加了 `_in_domain` CHECK，**`item` 没有**）。这是一个「库里存得下、算不出来」的不对称。

**这不是 Task 8 的缺陷**（我不改 `percentile.py`，它 Task 7 刚结案），也不是 Task 8 能解决的。但**必须写进 Task 10 派单**，否则 Task 10 到拼装 `derive` 实参时会发现 `snapshot_muscle_p20` 无从取值，只能填 `None`——而 `None` 会让肌肉量那一支**永远不成立**，`C` 退化成「只看体脂率」，且**全程不报错**（`test_muscle_below_p20_is_abnormal` 只在单元测试里覆盖了这一支）。

**请裁定**（Task 10 派单前）：
- **(A)** 扩 `ScoredItem`？——**不建议**，它会污染 `ITEM_WEIGHTS` / `WEAKNESS_ITEMS` / `ITEM_BUCKET` 与全部评分表查表逻辑；
- **(B)** 给 `PercentileSnapshot.item` 开一个「非国标计分项」的指标域（例如另加一列 `metric_kind`，或允许 `item` 取 `"muscle_mass_kg"` 并给 `compute_snapshot` 加一条不走 `ScoredItem` 的分支）——需要改 Task 7 的产物与 ORM，属设计变更；
- **(C)** 第一批**不实现**肌肉量那一支，`snapshot_muscle_p20` 一律传 `None`，并在 spec §6.3② 与 §14 明写「C 第一批只判体脂率」——最省事，但会让 `muscle_low` 这个 token 在生产上永不可达（而我已实现并有测试覆盖它），且与 spec §6.3② 的布尔式字面不符；
- **(D)** Task 10 自己用 `numpy.percentile` 就地算一次肌肉量 P20（不进快照表）——但这违反 spec §4.0「百分位必须物化为 `percentile_snapshot`，禁止实时计算」，会让分层结果无法复现任意一天的状态。

我倾向 **(B)**（它是唯一同时满足「物化」与「spec §6.3② 字面」的选项），但这超出 Task 8 的授权范围，**不自行实施**。

---

### 关切 9（Minor）— `test_derive_*` 5 条里没有一条断言 `DerivedResult.weakness` 与 `body_comp`

计划 Step 1 的 5 条 derive 测试断言的是 `trend`（3 条）、`annual_change`（4 条）、`national_total`（1 条）、`sex`（1 条）与两个异常（2 条）。**`r.weakness` 与 `r.body_comp` 一次都没被断言**——尽管 `derive` 的 docstring 与计划 `:1196` 都写明它要「依次调用 `classify_trend`、`find_weaknesses`、`flag_body_comp`」。

后果：`derive` 是否**真的**把体成分参数透传给了 `flag_body_comp`、是否真的调了 `find_weaknesses`，目前**没有任何测试守卫**。例如把 `derive` 里的 `flag_body_comp(body_fat_pct, muscle_mass_kg, sex, snapshot_muscle_p20)` 改成 `flag_body_comp(None, None, sex, None)`（即体成分数据被静默丢弃），**34 条测试会全绿**——而 `C` 会在全数据集上恒为 `False`，规则 R1 / Y2 永不触发，分层分布整体偏移。这与关切 1 的零覆盖是同一个缺口的两面。

**测量方法**：静态可复现——在 `derive` 里把 `body_comp = flag_body_comp(body_fat_pct, muscle_mass_kg, sex, snapshot_muscle_p20)` 改成 `body_comp = flag_body_comp(None, None, sex, None)`，跑 `pytest tests/domain/test_derive.py -q`，预期 **34 passed**（我没有真跑，因为这是第 5 次变异、超出简报要求的 4 次，且会再触发一次 checkout 行尾变化；若控制者要我实跑取证，一轮即可）。

**建议**：并入关切 1 的 (B) 选项，补 2–3 条断言（`r.weakness.count` / `r.weakness.dominant_bucket` / `r.body_comp.abnormal` 与 `r.body_comp.reasons`）。这属于「计划未列的测试」，故**本轮不自行添加**（简报 §4：不做本简报未要求的事）。

---

## 11. 临时探针清单与删除复核

本轮共创建 5 个临时文件，**全部已删除**，逐个 `Test-Path` 复核为 `False`：

| 文件 | 用途 | `Test-Path` |
|---|---|---|
| `backend\_probe_task8.py` | 500 人逐人对账明细 + `score_*` 诊断列交叉比对（§5.1 的输出） | **False** |
| `backend\_mk_commitmsg.py` | 生成无 BOM UTF-8 的 commit message 文件（PowerShell 无 heredoc） | **False** |
| `backend\_commitmsg_task8.txt` | `git commit -F` 的消息文件（114 字节，BOM: False，已核） | **False** |
| `backend\_probe2_task8.py` | 导出符号清单 / `annual_change` 键序 / `reasons` token vocabulary（§8 的输出） | **False** |
| `backend\tests\domain\_tmp_redcheck.py` | 复核 §3 里 pytest `Hint:` 行的逐字原文（同版 pytest 采集一个「导入不存在模块」的文件） | **False** |

复核命令与输出：

```
$ "probe py exists: $(Test-Path _probe_task8.py) / $(Test-Path _mk_commitmsg.py)"
probe py exists: False / False
$ git status --short
（空 —— 四个临时文件都是 untracked，删除后工作树回到干净；若残留会显示 ?? ）
```

关切 1 与关切 8 的两次测量用的是 `python -c` 一行命令，**没有创建文件**。

**未创建、未触碰的红线文件**：`backend/pe.db`（`Test-Path` → False）、`backend/data/seed/*`（0 个文件，目录保持空）、`backend/app/seed/*`（`git diff --stat 23f3468..HEAD -- backend/app/seed/` 为空）。

---

## 12. 前向约束（写进 Task 9 / Task 10 / Task 11 派单）

### 12.1 Task 9 消费 `DerivedResult` 时必须知道的事

1. **`valid_count < 4` 的闸门先于一切 W 规则**。`WeaknessResult.valid_count ≤ 6`，**两种**情形会让它 < 6：该项得分 `None`（缺测），或 `lookup_p25` 返回 `None`（该 (项, 性别, 年级组) 组没有快照行 = 没有判定线）。两者都**既不算短板也不进分母**，绝不当 0 分。`valid_count < 4` → `Layer.INSUFFICIENT`，**不进 R1/R2/Y1/Y2/Y3/Y4/G1 任何一条**（spec §6.2 末行）。
2. **`valid_count == 0` 时 `dominant_bucket is None`**，此时必须先走闸门（`0 < 4`）再去读 `dominant_bucket`，否则会对 `None` 做字符串匹配。`valid_count > 0` 时 `dominant_bucket` **恒非 None**。
3. **`dominant_bucket` 在 `W = 0` 时的口径**（Ruling 100，已实现并实测）：桶内**有效项得分均值**最低者 → 并列取桶内**最低单项得分**更低者 → 仍并列按 `_BUCKET_ORDER` 声明序 **`endurance` → `strength` → `speed_flexibility`**。`W > 0` 时：短板数最多的桶 → 并列取该桶内最低单项得分更低者 → 仍并列同上声明序。故**两级全并列时唯一答案是 `endurance`**，不依赖 dict 哈希顺序。18 套处方模板的「主导短板」维度直接用它。
4. **`annual_change == {}` 表示「无从比较」，不是「变化为 0」**。两种成因：无历史（`prev_scores is None`），或总分不可比（缺测，见关切 3）。`explain()` **不得**渲染「各项年均变化 0 分」。可比时**恰好 7 个键**，插入顺序为 `vital_capacity, sprint_50m, sit_and_reach, standing_jump, pull_up_or_sit_up, distance_run, national_total`（§8.1）。`"national_total"` 是字面量，本模块没有为它设常量。
5. **`body_comp.limit` 一律非 None**（男 `20.0` / 女 `28.0`），即使 `body_fat_pct is None`（Ruling 97②）——`explain()` 可以直接渲染「体成分数据缺失，本次不参与判定（男生阈值 20%）」，不需要为 `limit is None` 写分支。
6. **`reasons` 的 token vocabulary 恰好 2 个**：`"body_fat_high"`、`"muscle_low"`，顺序固定（先体脂率后肌肉量），`()` 表示正常。`abnormal == bool(reasons)` 恒成立，故 `explain()` 既可以按 `abnormal` 分支、也可以直接遍历 `reasons` 渲染，两者不会矛盾。中文文案由 `explain()` 按 token 渲染（Ruling 7），**新增第三个 token 必须先改 spec §6.3②**。
7. **Y4 只在 `derived.trend is Trend.DECLINING` 时触发**。`Trend.INSUFFICIENT`（无历史 **或** 总分不可得）**不触发** Y4（spec §6.3 表末行）。`Trend` 是 `str` 枚举，`Trend.STABLE == "稳定"` 直接成立；`Trend.INSUFFICIENT.value == "insufficient_data"`，与 Task 9 计划里的 `Layer.INSUFFICIENT = "insufficient_data"` **同字面量**——落库时注意别把两者混为一列（一个是趋势、一个是分层标签）。
8. **`DerivedResult.national_total` 可能为 `None`**（七项里有缺测）。同层内排序（spec §6.1 空洞一：进步榜、教师关注优先级）必须容忍 `None`，且**不得**把 `None` 当 0 排到最后——那会把缺测学生伪造成「最差」，与「缺测不当最坏值」（Ruling 21）相反。建议：`None` 者单独列「无法排序」一组。
9. **整数总分口径有一个已知偏向**（Ruling 95，本轮变异 3 侧面印证）：`//100` 对较小的 `Σw·curr` 向下取整，故整数口径**系统性地更容易判 DECLINING、更不容易判 IMPROVING**。Task 9 校准 20/45/35 分层分布时要知道这个偏向（它只影响 Y4 的触发人群，不影响 W/C 规则）。
10. **地板效应**（Task 6 移交，本轮已实测容忍）：28 名被标记男生的 `pull_up_or_sit_up` 两学年得分恒为 10、该项 delta 恒为 0。`classify_trend` 把 `d == 0` 既不计正也不计负，故这批人更难被判「波动大」。Task 9 的黄金用例须容忍两学年同为 10 分，且**不得**把「某项 delta 为 0」当作「稳定」的正向证据。

### 12.2 Task 10 调用 `derive` 时必须自己做的事

1. **必须自己先用 `national_total` 算好两个总分**再传进来：`curr_total = national_total(curr_scores)`、`prev_total = national_total(prev_scores)`。`derive` **不重算**（避免同一套加权出现在两处）。`national_total` 是加权口径的**唯一所有者**（Ruling 63），Task 10 的总分入库（`fitness_test_result.total_score`）也必须调它，**不得手写加权求和**；Task 6 的 `app.seed.fitness._weighted_total` 按计划 `:145` 的注记应在 Task 10 落地时删除并改用它。
2. **`curr_scores` / `prev_scores` 必须含全部 7 个计分项的键（含 `ScoredItem.BMI`）**，缺键 `KeyError`（Ruling 101）。只传 6 项会让 `national_total` **静默返回 `None`**，同层内排序在整个数据集上失效且不报错。
3. **`curr_total` 必须与 `curr_scores` 口径一致**：`curr_total is not None` ⇔ 七项都非 `None`，不一致 `ValueError`。
4. **`snapshot` 必须预筛到该生的 (性别, 年级组)**（关切 1 的 (B) 口径）：`[r for r in snapshot if r.sex == sex and r.age_group == age_group]`。传整张 24 行快照会 `ValueError`（响亮，不静默）。**若控制者裁定为关切 1 的 (A)，这一条作废、改为传 `age_group` 实参。**
5. **`snapshot_muscle_p20` 目前没有生产者**（关切 8），Task 10 派单前必须先裁定 (A)/(B)/(C)/(D)。传 `None` 会让 `muscle_low` 永不可达、`C` 退化成只看体脂率，且**不报错**。
6. **`years`** 是两次体测之间的学年差（相邻两学年 = `1.0`）。趋势阈值与 `annual_change` 都作用在**年均**量上，故 `years` 传错会同时错两处。
7. **喂给 `find_weaknesses` 的得分必须是清洗后正查出来的**（Ruling 21 / Task 7 前向约束）：`score_item` 对越界只做夹取、不判物理可能性，50 米跑 `0.0` 秒会正查出 **100 分**（低侧夹取对「越小越好」意味着低值得高分），一个缺测占位会给体能最差的学生送上 20% 权重的满分并抹掉两个桶的短板。清洗必须先于正查。
8. **判快照是否降级只看 `source`，不要用 `sample_size`**（Task 7 前向约束）：常模行是 `0`、降级行是真实人数。`p25` **可能是半分**（实测 24 组里 1 组 = 60.5），`find_weaknesses` 已按严格 `<` 处理，Task 10 不得假定 `p25` 是官方档位分。
9. **落库 `derived_metrics`** 时，`annual_change` 是「各指标年均变化率 JSON」列（spec §4.3），`{}` 与 7 键都要能存；`weakness.items` 是「短板列表 JSON」，存 `.value` 字符串；`body_comp.reasons` 是「C 的原因」，存 token 而不是中文文案。

### 12.3 Task 11（CLI）

无新增。本轮不碰 CLI、不碰数据库、不落库（Task 10 的事）。

---

## 13. 末尾取证

```
$ git log --oneline -1
2a51aad feat: 派生指标 — 趋势四分类、短板与主导桶、体成分异常，总分口径统一为国标加权

$ git status --short
（空）
```

报告文件本身的落盘复核见下方追加段（写入后以 `(Get-Item <report>).Length` 取证）。
