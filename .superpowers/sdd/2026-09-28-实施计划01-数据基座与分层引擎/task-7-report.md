# Task 7 实现者报告 — 校内百分位快照

**状态：DONE_WITH_CONCERNS**
**commit：`6b68da8`** — `feat: 校内同龄同性别百分位快照，样本不足30人降级为按评分表推导的国标常模并留痕`
基线 `c72b53f`，分支 `feature/plan-01-data-foundation`，**一个** commit，2 files changed / 347 insertions：

```
create mode 100644 backend/app/domain/percentile.py
create mode 100644 backend/tests/domain/test_percentile.py
```

不含任何 CSV。`git status --short` 为空（见文末）。

代码本身照计划 Step 1–6 落地、全绿、变异验证有效；「WITH_CONCERNS」来自**控制者文档里的两组数字与实测不符**（关切 1、2）、**一处契约里被接收却不使用的键**（关切 3）、**兜底假设的逐组偏差幅度**（关切 4）、**简报对变异结果的预期有误**（关切 5），以及三处指路牌问题与一次写盘事故（关切 6、7）。**没有一条要求改动本轮已提交的代码。**

---

## 1. 测试数与洁净度

| 项 | 结果 |
|---|---|
| 基线（Task 1–6 结案） | **318 passed** in 9.80s |
| 本轮新增 | `tests/domain/test_percentile.py` **10 条** |
| 结束时全量 | **328 passed** in 9.72s |
| 结束时全量 `-W error` | **328 passed** in 9.74s（洁净，无 warning 被提升为 error） |
| 三次变异全部还原后复跑 | `pytest -q` **328 passed** in 10.25s；`pytest -q -W error` **328 passed** in 9.82s |
| 交付前最后一次复跑 | `pytest -q` **328 passed** in 9.69s |
| 既有 318 条断言 | **未改一字**（`git diff --stat c72b53f..HEAD` 只含两个 `create mode` 新文件） |

## 2. Step 2 的 RED 输出

```
============================= test session starts =============================
platform win32 -- Python 3.11.1, pytest-9.1.1, pluggy-1.6.0 -- C:\Python\python.exe
rootdir: C:\Users\whwenhao\Desktop\Physical_Education_ims\backend
configfile: pyproject.toml
collecting ... collected 0 items / 1 error

=================================== ERRORS ====================================
______________ ERROR collecting tests/domain/test_percentile.py _______________
ImportError while importing test module 'C:\...\backend\tests\domain\test_percentile.py'.
Traceback:
C:\Python\Lib\importlib\__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
tests\domain\test_percentile.py:3: in <module>
    from app.domain.percentile import (
E   ModuleNotFoundError: No module named 'app.domain.percentile'
=========================== short test summary info ===========================
ERROR tests/domain/test_percentile.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.26s ===============================
```

与计划 Step 2 的 Expected 一致。

## 3. Step 5 的 GREEN 输出

```
collected 10 items

tests/domain/test_percentile.py::test_snapshot_groups_by_sex_age_item PASSED [ 10%]
tests/domain/test_percentile.py::test_percentile_values_are_ordered PASSED [ 20%]
tests/domain/test_percentile.py::test_snapshot_falls_back_to_national_when_sample_below_30 PASSED [ 30%]
tests/domain/test_percentile.py::test_fallback_row_equals_national_norm_exactly PASSED [ 40%]
tests/domain/test_percentile.py::test_snapshot_uses_school_when_sample_reaches_30 PASSED [ 50%]
tests/domain/test_percentile.py::test_lookup_p25_returns_none_when_group_absent PASSED [ 60%]
tests/domain/test_percentile.py::test_national_norm_covers_every_weakness_item_sex_and_grade_group PASSED [ 70%]
tests/domain/test_percentile.py::test_national_norm_percentiles_are_monotone_for_every_group PASSED [ 80%]
tests/domain/test_percentile.py::test_national_norm_direction_is_read_from_the_table_not_hardcoded PASSED [ 90%]
tests/domain/test_percentile.py::test_national_norm_needs_no_file_beyond_the_standard_table PASSED [100%]

============================= 10 passed in 0.20s ==============================
```

**10 passed**，与计划 Step 5 修正后的期望数一致（Ruling：`6 passed` → `10 passed`）。

## 4. AST 纯净性守卫（`pytest tests/architecture -v`）

```
collected 3 items

tests/architecture/test_domain_purity.py::test_domain_has_no_forbidden_imports PASSED [ 33%]
tests/architecture/test_domain_purity.py::test_domain_has_no_clock_or_file_access PASSED [ 66%]
tests/architecture/test_domain_purity.py::test_domain_has_no_filesystem_access PASSED [100%]

============================== 3 passed in 0.02s ==============================
```

新增的 `app/domain/percentile.py` 被这三个守卫扫描且全绿。该模块的 import 只有
`dataclasses` / `numpy` / `app.domain.indicators` / `app.domain.tables`——**没有 `app.refdata`**（Ruling 87），
`table` 一律由调用方显式传参。

> 但守卫本身拦不住「import 一个会读盘的模块」（简报 §2④ 已指出），所以这条纪律在
> `percentile.py` 的模块 docstring 与 `national_norm` / `compute_snapshot` 两处 docstring 里都写了理由，
> 并由签名强制（两个函数的首参都是 `table: StandardTable`）。

## 5. `backend/app/seed/` 未被触碰的证明

```
$ git diff --stat c72b53f..HEAD -- backend/app/seed/
(无输出)
```

**为空**，即 Task 6 结案的 7 个生成器文件本轮零改动，三个 CSV 的哈希不受影响。

另外两条环境纪律的复核：

```
$ Test-Path backend\pe.db                                   → False   （Ruling 68：未创建、未触碰）
$ Get-ChildItem backend\data\seed -Force | Measure-Object   → Count 0 （保持空目录）
```

本轮**没有新增任何数据文件**；`backend/data/` 仍是原有的三项
（`README_national_standard.md`、`indicator_ranges.yaml`、`national_standard_2014.csv`）。
探针输出写在 `%TEMP%\task7_probe_out.txt` / `task7_probe2_out.txt`，不在仓库内。

## 6. 24 组国标常模的实测五档全表

来源：直接调用**生产代码** `national_norm(standard(), item, sex, age_group)`（不是重新推导）。
`PERCENTILES = (10, 20, 25, 50, 75)`，`MIN_SAMPLE = 30`。

| item | sex | age_group | P10 | P20 | P25 | P50 | P75 | sample_size | source |
|---|---|---|---|---|---|---|---|---|---|
| vital_capacity | male | 大一、大二 | 20 | 40 | **50** | 68 | 80 | 0 | national |
| vital_capacity | male | 大三、大四 | 20 | 40 | **50** | 68 | 80 | 0 | national |
| vital_capacity | female | 大一、大二 | 50 | 62 | **64** | 72 | 80 | 0 | national |
| vital_capacity | female | 大三、大四 | 50 | 62 | **64** | 72 | 80 | 0 | national |
| sprint_50m | male | 大一、大二 | 20 | 40 | **50** | 66 | 74 | 0 | national |
| sprint_50m | male | 大三、大四 | 20 | 40 | **50** | 66 | 74 | 0 | national |
| sprint_50m | female | 大一、大二 | 20 | 40 | **50** | 68 | 78 | 0 | national |
| sprint_50m | female | 大三、大四 | 20 | 40 | **50** | 68 | 78 | 0 | national |
| sit_and_reach | male | 大一、大二 | 30 | 60 | **62** | 70 | 80 | 0 | national |
| sit_and_reach | male | 大三、大四 | 30 | 60 | **62** | 70 | 80 | 0 | national |
| sit_and_reach | female | 大一、大二 | 30 | 60 | **62** | 72 | 80 | 0 | national |
| sit_and_reach | female | 大三、大四 | 30 | 60 | **62** | 72 | 80 | 0 | national |
| standing_jump | male | 大一、大二 | 20 | 40 | **50** | 70 | 80 | 0 | national |
| standing_jump | male | 大三、大四 | 20 | 40 | **50** | 70 | 80 | 0 | national |
| standing_jump | female | 大一、大二 | 20 | 40 | **50** | 70 | 80 | 0 | national |
| standing_jump | female | 大三、大四 | 20 | 40 | **50** | 70 | 80 | 0 | national |
| pull_up_or_sit_up | male | 大一、大二 | 20 | 30 | **40** | 68 | 80 | 0 | national |
| pull_up_or_sit_up | male | 大三、大四 | 20 | 30 | **40** | 68 | 80 | 0 | national |
| pull_up_or_sit_up | female | 大一、大二 | 30 | 50 | **60** | 70 | 80 | 0 | national |
| pull_up_or_sit_up | female | 大三、大四 | 30 | 50 | **60** | 70 | 80 | 0 | national |
| distance_run | male | 大一、大二 | 10 | 20 | **30** | 50 | 72 | 0 | national |
| distance_run | male | 大三、大四 | 10 | 20 | **30** | 50 | 72 | 0 | national |
| distance_run | female | 大一、大二 | 20 | 30 | **40** | 64 | 76 | 0 | national |
| distance_run | female | 大三、大四 | 20 | 30 | **40** | 64 | 76 | 0 | national |

**逆序核对：组数 = 24，逆序组数 = 0**（逐组检查 `p10 ≤ p20 ≤ p25 ≤ p50 ≤ p75`，全部单调不减）。
与控制者预检的「24 组逆序 0 组」**一致**。

**国标 P25 范围：实测 `30 .. 64`**，去重取值 `{30, 40, 50, 60, 62, 64}`。
控制者预检记的是 **40–64** —— **下界不符，见关切 1**。

两个年级组在同一 (项, 性别) 下五档完全相同：这不是缺陷，而是因为国标 2014 大学两个年级组
的评分阈值序列在这 6 项上**首末阈值相同且档位分序列同构**，故均匀假设下的分位落点相同。
（若换成真实常模，两个年级组本应不同——这也是「假设是占位」的一个具体表现。）

### 方向感知的交叉验证（与控制者的第一版探针对账）

简报 §2① 记：控制者第一版探针没做方向感知，得到 `P10=80 > P25=74 > P50=66 > P75=50`。
我在生产代码上把方向感知**临时去掉**（变异 A，见 §8），实测 `sprint_50m / male / 大一、大二`
得到 **`p10=80.0, p20=76.0, p25=74.0, p50=66.0, p75=50.0`** —— 与控制者记的四个数**逐位相同**。
计划 Step 1 的注释又记「把方向判断写反，这两项的 P25 会从 **50 / 30** 跳到 **74 / 72**」，
实测同样是 `sprint_50m` 50→74、`distance_run` 30→72，**四个数逐位相同**。

即：本轮的推导实现与控制者预检时的推导在数值上完全同构，方向感知这一承重部分已验证到位。

`distance_run / male / 大一、大二` 的推导逐项细节（读生产 `segment_thresholds` + `score_item`）：

```
档数 = 20   lo = 197.0 s   hi = 372.0 s   span = 175
score_item(lo) = 100   score_item(hi) = 10   → lower_is_better = True（从表推断，未按项硬编码）
P10: q = 100-10 = 90   raw = 354.5000   score_item = 10    | 若方向写反 q=10 raw=214.5000 score=80
P20: q = 100-20 = 80   raw = 337.0000   score_item = 20    | 若方向写反 q=20 raw=232.0000 score=76
P25: q = 100-25 = 75   raw = 328.2500   score_item = 30    | 若方向写反 q=25 raw=240.7500 score=72
P50: q = 100-50 = 50   raw = 284.5000   score_item = 50    | 若方向写反 q=50 raw=284.5000 score=50
P75: q = 100-75 = 25   raw = 240.7500   score_item = 72    | 若方向写反 q=75 raw=328.2500 score=30
生产 national_norm(...).p25 = 30.0
```

## 7. `national_norm` 与 500 人真实生成数据本校 P25 的逐组对照

**数据来源（全部生产状态，无一处重新推导）**：
`build_dataset(SeedConfig())`（Task 6 的生产生成器，默认 `seed=20250828`、`students=500`）
→ `population` 提供 `sex` / `age`，`age_group_of(age)` 折算年级组
→ `fitness` 记录里的 `score_<item>` 七列（生成期的国标单项得分）
→ 组装成 `compute_snapshot` 契约形状的 `scores` 列表 → 喂给**生产的** `compute_snapshot(scores, standard())`。

**切片**：本学年 `academic_year = "2025-2026"`、`timepoint = "week16"`，共 **508 行**
（500 人 + 8 条 Task 6 按 1% 注入的 duplicate 记录；见关切 3）。
全 6 项 × 2 性别 × 2 年级组 = **24 组**（超出简报要求的「至少 3 项 × 2 性别 × 2 年级组」）。
喂入的得分条数 3048（缺测的 `score_*` 为 `None` 时跳过）。

| item | sex | age_group | n | 本校 P25 | 国标 P25 | 差 | 本校 P10 | 本校 P75 |
|---|---|---|---|---|---|---|---|---|
| vital_capacity | male | 大一、大二 | 159 | 62 | 50 | +12 | 40 | 80 |
| vital_capacity | male | 大三、大四 | 122 | 64 | 50 | +14 | 50 | 80 |
| vital_capacity | female | 大一、大二 | 121 | 60 | 64 | −4 | 50 | 80 |
| vital_capacity | female | 大三、大四 | 106 | 62 | 64 | −2 | 50 | 80 |
| sprint_50m | male | 大一、大二 | 159 | 50 | 50 | 0 | 40 | 80 |
| sprint_50m | male | 大三、大四 | 122 | 62 | 50 | +12 | 50 | 85 |
| sprint_50m | female | 大一、大二 | 121 | 62 | 50 | +12 | 50 | 80 |
| sprint_50m | female | 大三、大四 | 106 | 60 | 50 | +10 | 40 | 80 |
| sit_and_reach | male | 大一、大二 | 159 | 55 | 62 | −7 | 40 | 80 |
| sit_and_reach | male | 大三、大四 | 122 | 62 | 62 | 0 | 50 | 80 |
| sit_and_reach | female | 大一、大二 | 121 | 64 | 62 | +2 | 50 | 80 |
| sit_and_reach | female | 大三、大四 | 106 | 60 | 62 | −2 | 45 | 80 |
| standing_jump | male | 大一、大二 | 159 | 60 | 50 | +10 | 50 | 80 |
| standing_jump | male | 大三、大四 | 122 | 62 | 50 | +12 | 50 | 80 |
| standing_jump | female | 大一、大二 | 121 | 62 | 50 | +12 | 50 | 80 |
| standing_jump | female | 大三、大四 | 106 | **60.5** | 50 | +10.5 | 50 | 78 |
| pull_up_or_sit_up | male | 大一、大二 | 159 | 60 | 40 | +20 | 10 | 80 |
| pull_up_or_sit_up | male | 大三、大四 | 122 | 60 | 40 | +20 | 50 | 80 |
| pull_up_or_sit_up | female | 大一、大二 | 121 | 62 | 60 | +2 | 50 | 80 |
| pull_up_or_sit_up | female | 大三、大四 | 106 | 60 | 60 | 0 | 45 | 80 |
| distance_run | male | 大一、大二 | 159 | 60 | 30 | **+30** | 50 | 80 |
| distance_run | male | 大三、大四 | 122 | 64 | 30 | **+34** | 50 | 85 |
| distance_run | female | 大一、大二 | 121 | 60 | 40 | +20 | 50 | 80 |
| distance_run | female | 大三、大四 | 106 | 60 | 40 | +20 | 50 | 80 |

汇总结论：

- `compute_snapshot` 产出 **24 行**，`source` 分布 = `{"school": 24, "national": 0}`。
- 本校 `sample_size` 范围 **106 .. 159**，**小于 `MIN_SAMPLE`(30) 的组数 = 0** ——
  印证 spec §14 #24 的影响面判断：「500 人规模下四组均 ≥30，故生产数据实际不走这条兜底」。
- **本校 P25 范围（本切片）= 50 .. 64**；国标 P25 范围 = 30 .. 64。**量级相同**（同一 0–100 得分尺度、
  同一档位分集合、区间大幅重叠），作为兜底**可比**。
- 逐组差 `(本校 − 国标)` 范围 **−7 .. +34**，均值 **+9.90**。差不是均匀分布的：
  `distance_run` 四组 +20 ~ +34、`pull_up_or_sit_up` 男两组 +20 —— **见关切 4**。
- **本校 P25 为半分（非整数）的组数 = 1 / 24**（`standing_jump / female / 大三、大四 = 60.5`）。
  这坐实了 Step 4 要求写进 docstring 的 ties 后果：`method="linear"` 在离散得分上确实会给出半分，
  下游不得假定 `p25` 是官方档位分。

### 本校 P25 对「用哪一批数据」的敏感性（为关切 2 取证）

同一份 `build_dataset(SeedConfig())`，换切片后重跑生产 `compute_snapshot`：

| 切片 | 行数 | 本校 P25 全组 min..max | 肺活量男大一二 | 坐位体前屈男大一二 |
|---|---|---|---|---|
| 2024-2025 week1 | 506 | **40** .. 62 | 50 | 50 |
| 2024-2025 week8 | 503 | **40** .. 62 | 50 | 50 |
| 2024-2025 week16 | 502 | 50 .. **64** | 50 | 50 |
| 2025-2026 week1 | 505 | **50 .. 62** | **50** | **50** |
| 2025-2026 week8 | 508 | 50 .. **64** | 60 | 50 |
| 2025-2026 week16 | 508 | 50 .. **64** | 62 | 55 |
| 全部 3032 行合并 | 3032 | **50 .. 62** | **50** | **50** |

控制者在 progress.md `### Task 7` 记的两个具体值「肺活量男大一二 school **50.0** / national 50，
坐位体前屈男大一二 school **50.0** / national 62」与「本校 P25 落在 **50–62**」，
在 **`2025-2026 week1`** 与 **`全部行合并`** 两个切片上**逐位复现**（加粗行）。
national 侧的 50 与 62 在**所有**切片上都复现（它只依赖评分表，与数据切片无关）。
**跨 7 个切片的本校 P25 全距是 40 .. 64，不是 50 .. 62。**

## 8. 变异验证（三次，均完全还原）

三次变异都作用在**生产文件** `backend/app/domain/percentile.py`，每次都用
`Select-String -SimpleMatch` 先确认变异字节真的落盘（行号 + 内容），再跑测试。

### 变异 A — 去掉方向感知（`q = p` 恒定）

落盘确认：`132: lo + span * p / 100.0,  # MUTATION_A`
（原为 `lo + span * ((100 - p) if lower_is_better else p) / 100.0,`）

结果：**3 failed, 7 passed**

```
FAILED ...::test_national_norm_percentiles_are_monotone_for_every_group
       - AssertionError: assert False  (all(<genexpr>))
FAILED ...::test_national_norm_direction_is_read_from_the_table_not_hardcoded
       - AssertionError: assert 72.0 == 30
         where 72.0 = PercentileRow(item=DISTANCE_RUN, sex=MALE, age_group='大一、大二',
                        p10=80.0, p20=76.0, p25=72.0, p50=50.0, p75=30.0,
                        sample_size=0, source='national').p25
FAILED ...::test_national_norm_needs_no_file_beyond_the_standard_table
       - AssertionError: [70.0, 70.0, 70.0, 40.0, 40.0]  (all(<genexpr>) is False)
```

- 简报 §5 预期变红的两条（单调性 + 方向从表推断）**都红了** ✓。
- 失败信息里的 `p10=80.0 > p20=76.0 > p25=72.0 > p50=50.0 > p75=30.0` 正是简报 §2① 描述的
  **递减序列**，与 §6 的对账一致。
- **额外收获**：第 10 条测试（我从 `...` 占位真正实现的那条）也红了。它的迷你表是
  **越小越好**的 50 米跑（`raw` 升序 6.5/7.5/9.0 对应 `score` 降序 100/70/40），
  去掉方向感知后五档变成 `[70,70,70,40,40]` —— 递减，被该测试内的单调性断言抓住。
  即这条测试不只是「证明不读第二份文件」，它**同时是一条独立的方向守卫**，
  而且是在一张真表造不出来的 3 档形状上守的。

### 变异 B — `MIN_SAMPLE` 比较符 `<` → `<=`

落盘确认：`189: if len(group) <= MIN_SAMPLE:  # MUTATION_B`

结果：**1 failed, 9 passed**

```
FAILED ...::test_snapshot_uses_school_when_sample_reaches_30
       - AssertionError: assert 'national' == 'school'
           - school
           + national
```

**与简报 §5 的预期不符**：简报要求「断言 Review Focus #4 那两条变红」，实测只红了 **1 条**，
且红的是上边界那条（`..._uses_school_when_sample_reaches_30`），
而 Review Focus #4 点名的 `test_snapshot_falls_back_to_national_when_sample_below_30` **没有变红**。
原因是可复现的、且与实现无关：该测试只探 `n = MIN_SAMPLE - 1 = 29`，
而 29 在 `<` 与 `<=` 两种口径下**落在同一侧**，故它对这一变异天然不敏感。**详见关切 5。**

### 变异 C（补做）— 阈值下移一格 `< MIN_SAMPLE` → `< MIN_SAMPLE - 1`

落盘确认：`189: if len(group) < MIN_SAMPLE - 1:  # MUTATION_C`

结果：**2 failed, 8 passed**

```
FAILED ...::test_snapshot_falls_back_to_national_when_sample_below_30
       - AssertionError: assert 'school' == 'national'
FAILED ...::test_fallback_row_equals_national_norm_exactly
       - assert (11.0, ..., 49.0, 75.0) == (20.0, 40.0, 50.0, 66.0, 74.0)
```

**恰好是 Review Focus #4 那两条**。B 与 C 合起来证明：三条边界测试各自守一侧 off-by-one，
`MIN_SAMPLE` 的边界被**双向**钉住，没有一条是装饰。

### 还原证据

三次变异后各执行 `git checkout -- backend/app/domain/percentile.py`，逐项复核：

| 复核项 | 变异 A 还原后 | 变异 B 还原后 | 变异 C 还原后 |
|---|---|---|---|
| `MUTATION_A` 命中数 | **0** | — | — |
| `MUTATION_B` 命中数 | — | **0** | — |
| `MUTATION_C` 命中数 | — | — | **0** |
| `git diff --stat` | **空** | **空** | **空** |
| `git status --short` | **空** | **空** | **空** |
| `percentile.py` SHA256 | `C4E8A1EE…048AC5` | `C4E8A1EE…048AC5` | `C4E8A1EE…048AC5` |
| 全量测试 | 328 passed | — | **328 passed** + `-W error` **328 passed** |

（三个标记在最终状态下一次性复查，命中数全为 0。）

> **SHA256 的一个坑，记下来供后续 Task 复用**：提交**前**测得的 `percentile.py` 哈希是
> `F5747E7A…ABFD`，`git checkout` **还原后**变成 `C4E8A1EE…48AC5`。两者都是正确状态——
> 差异纯粹来自 git 的行尾归一化（commit 时 git 就警告过
> `warning: in the working copy of 'backend/app/domain/percentile.py', LF will be replaced by CRLF the next time Git touches it`；
> 写文件工具落的是 LF，`git checkout` 恢复的是 CRLF）。
> **所以「还原是否彻底」不能拿提交前的哈希当基准**，必须拿
> 「`git diff --stat` 为空 + `git status --short` 为空 + 变异标记 0 命中 + 还原后哈希在多次还原间自洽」
> 这四条一起判。本轮三次还原得到的是**同一个** `C4E8A1EE…`，且工作树与 `6b68da8` 零差异。

## 9. 关切

> 每条都附可复现方法，并标注该方法读的是**生产代码/生产数据的中间状态**还是**我重新推导的输入**。
> 下面 7 条里**没有一条要求改动本轮已提交的代码**；关切 1、2 指向控制者文档（含已提交的 spec §14 #24）里的数字，
> 关切 5 指向简报对变异结果的预期。

### 关切 1（承重，控制者文档数字有误）— 国标 P25 的实际范围是 **30–64**，不是 40–64

**原文摘要**：简报 §2① 与 progress.md Ruling 84 都写「国标 P25 落在 **40–64**」；
已提交的 spec §14 **#24**（`Document/2026-09-28-体育闭环原型-设计spec.md:862`）同样写
「实测 24 组逆序 0 组、国标 P25 落在 **40–64**」。实测下界是 **30**，来自
`distance_run / male / 大一、大二` 与 `distance_run / male / 大三、大四` 两组。

**这不是我的实现偏离了裁定，而是裁定文档里的数字与裁定自身的另一处正文自相矛盾**：
计划 Step 1 中 `test_national_norm_direction_is_read_from_the_table_not_hardcoded` 的注释写
「把方向判断写反，这两项的 P25 会从 **50 / 30** 跳到 74 / 72」——**这个 30 就是耐力跑男的 P25**，
与我的实测一致，与同一批文档里的「40–64」不一致。三处（简报 §2①、Ruling 84、spec §14 #24）
的 40 疑为把 `distance_run / female` 的 40 误当成了全表下界，或把 `pull_up_or_sit_up / male` 的 40 记串了。

**可复现方法（读生产代码，非重新推导）**：

```python
# cd backend; python
from app.refdata import standard
from app.domain.percentile import national_norm
from app.domain.indicators import WEAKNESS_ITEMS, Sex, AGE_GROUPS, ScoredItem
ps = [national_norm(standard(), i, s, a).p25
      for i in WEAKNESS_ITEMS for s in (Sex.MALE, Sex.FEMALE) for a in AGE_GROUPS]
min(ps), max(ps)                                            # 实测 (30.0, 64.0)
national_norm(standard(), ScoredItem.DISTANCE_RUN, Sex.MALE, AGE_GROUPS[0]).p25   # 实测 30.0
```

更细的推导链（同样是生产函数）：`segment_thresholds(standard(), DISTANCE_RUN, MALE, "大一、大二")`
→ `lo = 197.0`、`hi = 372.0`；P25 走 `q = 100 − 25 = 75` → `raw = 197.0 + 175 × 0.75 = 328.25`；
`score_item(standard(), DISTANCE_RUN, 328.25, MALE, "大一、大二")` → **30**。
§6 的 24 行全表即该循环的完整输出。

**影响**：不影响本轮代码与测试（没有任何断言依赖 40 这个下界）。
影响的是**对账**——控制者若拿「40–64」跟本报告对账，会以为下界差了 10 分而误判实现有缺陷；
以及 spec §14 #24 那句已提交的文字需要更正为 30–64。**我没有改 spec**（不在本轮授权范围内）。

### 关切 2（控制者文档口径不完整）— 「本校 P25 落在 50–62」是**某一个切片**的性质，不是数据集的性质

**原文摘要**：简报 §2① 与 Ruling 84 写「500 人真实生成数据的本校 P25（**50–62**）」，
spec §14 #24 同样写「500 人仿真数据的本校 P25（50–62）」。
实测：该区间只在 **`2025-2026 week1`** 与 **`全部 3032 行合并`** 两个切片上成立；
**跨 7 个切片的全距是 40 .. 64**（`2024-2025 week1/week8` 的 min 是 **40**，
`2024-2025 week16`、`2025-2026 week8/week16` 的 max 是 **64**）。

**我已定位到控制者用的是哪个切片**：progress.md 记的两个具体值
「肺活量男大一二 school **50.0**、坐位体前屈男大一二 school **50.0**」在上述两个切片上**逐位复现**，
在其余五个切片上至少一个不符（例如 `2025-2026 week16` 是 62 与 55）。
所以这不是「数字对不上」，而是**引用时漏了切片条件**——而 500 人 × 两学年 × 三时点的数据集有 6 个自然切片，
不写明用哪一个，这句话无法被后来人复核。

**可复现方法（读生产状态：Task 6 的生产生成器 + 本轮生产 `compute_snapshot`）**：见 §7 的敏感性表。
探针脚本的核心几行（`build_dataset` 是生产函数，`score_<item>` 是生成器自己写进记录的列，我没有重新推导任何输入）：

```python
ds = build_dataset(SeedConfig())                      # 生产生成器，seed=20250828
people = {p["student_id"]: p for p in ds["population"]}
rows = [r for r in ds["fitness"]
        if r["academic_year"] == year and r["timepoint"] == tp]     # 换 (year, tp) 即换切片
scores = [{"student_id": r["student_id"], "sex": people[r["student_id"]]["sex"],
           "age_group": age_group_of(people[r["student_id"]]["age"]),
           "item": item, "score": int(r[f"score_{item.value}"])}
          for r in rows for item in WEAKNESS_ITEMS
          if r[f"score_{item.value}"] is not None]
snap = compute_snapshot(scores, standard())           # 生产函数
```

**建议**：spec §14 #24 与 progress.md Ruling 84 补上切片口径（例如「本学年 week1」或「全部行合并」），
或改写成跨切片全距 40–64。**「同量级、作为兜底可比」这个结论在两种口径下都成立**
（国标 30–64 vs 本校 40–64，同一尺度、区间大幅重叠），所以这不是承重缺陷，是可复核性问题。

### 关切 3（契约缺陷，与 Ruling 86 同构）— `scores` 里的 `student_id` 被接收却从未使用

**原文摘要**：计划 Task 7 Interfaces 定义 `scores` 每项为
`{"student_id": int, "sex": str, "age_group": str, "item": ScoredItem, "score": int}`。
分组键是 `(sex, age_group, item)`，百分位只吃 `score` —— **`student_id` 在整个
`compute_snapshot` 里没有任何用处**。这与 Ruling 86 删掉 `computed_on` 的理由**逐字同构**：
「一个被接收然后被丢弃的参数是撒谎：调用方会以为它被记录了」。
这里调用方会以为它被用来**按人去重**了，而实际上没有。

**可复现方法（读生产代码）**：

```powershell
Select-String -Path backend\app\domain\percentile.py -Pattern "student_id" -SimpleMatch | Measure-Object
# Count = 0 —— 生产模块里根本没出现这个键名
```

**实测后果（读生产数据）**：Task 6 按 `cfg.dirty["duplicate"] = 0.01` 注入重复记录，
`build_dataset(SeedConfig())` 的 `fitness` 共 **3032 行**（500 人 × 2 学年 × 3 时点 = 3000，多出 **32 行**即重复），
本学年 week16 切片 **508 行**（500 + 8）。这些重复行会被 `compute_snapshot` 当作**独立样本**计入
`sample_size` 与百分位——同一个学生的一票被数了两次。
生产路径上 Task 5 的清洗层会去重（`duplicate` 是四类脏数据之一），故 Task 10 传进来的数据应当已无重复，
**所以这不是缺陷**；但契约里留着一个不用的键，会让下一个实现者以为去重已经在这里发生了。

**两种处置（我不擅自选）**：① 从 `scores` 的文档化形状里删掉 `student_id`（与 Ruling 86 一致的做法）；
② 让 `compute_snapshot` 按 `(student_id, item)` 去重，把「一人一票」变成机制而不是纪律
（Task 6 的 Ruling 29 正是这个思路：「纪律会被下一次重构悄悄改掉，约束不会」）。
**本轮照计划的契约实现，未做任何一种改动。**

### 关切 4（假设的后果，建议记进 spec §14 #24 的影响面）— 兜底常模在耐力跑上系统性低于本校线 20–34 分

**原文摘要**：Ruling 84 的论证是「国标 P25 40–64 与本校 P25 50–62 **同量级，作为兜底可比**」。
在**区间**层面这成立；但在**逐组**层面，差值分布极不均匀：
`(本校 P25 − 国标 P25)` 实测范围 **−7 .. +34**、均值 **+9.90**，其中
`distance_run` 四组分别是 **+30 / +34 / +20 / +20**，`pull_up_or_sit_up` 男两组各 **+20**。
方向是「常模比本校**宽松**」：P25 越低，`score < p25` 命中的人越少。

**研究后果**：某个 (性别 × 年级组 × 项目) 分组样本 < 30 而降级时，
**耐力跑短板会被系统性少判最多 34 分对应的整段人群**，而耐力跑权重 **20%**（与 50 米跑并列 7 项中最高，
`ITEM_WEIGHTS`），`ITEM_BUCKET` 里它又占 `endurance` 桶的一半。
`W` 被压低 → R1/R2/Y3 触发率下降 → 红色层被低估。这与 Task 6 为
`sub_floor_rate` 写的理由（「不生成表下溢出会让力量维度低尾被截断 → 校内 P25 偏高 → 短板识别偏少 →
红色层被系统性低估」）是**同一类偏差，只是方向相反、来源不同**。

**根因不是实现缺陷**，是 Ruling 84 那个「均匀分布于量程 `[lo, hi]`」假设的直接后果：
耐力跑的官方得分阶梯在**慢端密集**（`lo=197s → 100 分`，`hi=372s → 10 分`，
但 P25 落在 `328.25s` 只得 30 分），均匀假设把过多人群放到了高分区，于是低分位被压得很低。

**可复现方法（读生产代码）**：§7 那张 24 行对照表的「差」列即逐组结果；
单组最小复现见关切 1 的 `distance_run / male` 推导链（`national_norm` → 30，
`compute_snapshot` 在 `2025-2026 week16` 切片上 → 60）。

**建议**：spec §14 #24 的影响面一栏目前写的是
「500 人规模下四组均 ≥30，故生产数据实际不走这条兜底，影响面限于小规模部署与降级路径的测试」——
这句在**触发概率**上是对的（§7 已实测：24 组 n = 106..159，0 组降级），
但漏了**触发后的偏差幅度与方向**。建议补一句：「降级后耐力跑与男子力量项的判定线会比校内口径低 20–34 分，
即短板被系统性少判；小规模部署若关心这两项，应优先补样本而非依赖兜底」。
**我没有改 spec。**

### 关切 5（测试敏感度，与简报 §5 的预期不符）— 变异 B 只让 **1 条**变红，不是简报预期的 2 条

**原文摘要**：简报 §5 要求「(b) 把 `MIN_SAMPLE` 的比较符从 `<` 改成 `<=`，
断言 **Review Focus #4 那两条**变红」。实测 **1 failed, 9 passed**，红的是
`test_snapshot_uses_school_when_sample_reaches_30`（上边界），
而 Review Focus #4 点名的 `test_snapshot_falls_back_to_national_when_sample_below_30` **不红**。

**原因是可证的、与实现无关**：该测试只探 `n = MIN_SAMPLE − 1 = 29`，
29 在 `<` 与 `<=` 下**同侧**（都触发降级），故它对这一变异天然不敏感。
**这不是测试写弱了**——我补做的**变异 C**（`< MIN_SAMPLE` → `< MIN_SAMPLE - 1`，即阈值下移一格）
让它和 `test_fallback_row_equals_national_norm_exactly` **恰好双双变红**（2 failed, 8 passed）。
即：三条边界测试各自守一侧 off-by-one，B 守上侧、C 守下侧，**边界被双向钉住**。
简报把「哪一侧的变异会红哪两条」记串了。

**可复现方法（读生产代码 + 生产测试）**：§8 变异 B / C 两小节，含落盘行号、变异前后源码、
pytest 短摘要原文。还原证据见 §8 末表。

**建议**：把这条记进 progress.md，供后续 Task 引用「变异验证」时不要把
「预期红哪几条」当成已知事实转引——本轮的实测是：**去方向感知红 3 条（比预期多 1 条）、
比较符 `<`→`<=` 红 1 条（比预期少 1 条）、阈值 −1 红 2 条**。

### 关切 6（三处指路牌/口径问题，均已绕过，不影响交付）

**① 迷你表的造法不在 `test_indicators.py`。**
简报 §1 第 6 条与计划 Step 1 第 10 条测试的注释都说：
「照 `tests/domain/test_indicators.py` 里 `T` 的造法（`refdata.load_standard` 读 tmp_path 下的迷你 CSV）」。
实测该文件里的 `T` 是 **`T = standard()`（真表进程内单例，`test_indicators.py:10`）**，
全文**没有** `tmp_path`、也**没有** `load_standard`：

```powershell
Select-String -Path backend\tests\domain\test_indicators.py -Pattern "tmp_path|load_standard|\.csv" | Measure-Object
# Count = 0
```

「写迷你 CSV 到 `tmp_path` 再 `refdata.load_standard(path)`」这个造法实际在
**`backend/tests/test_refdata.py:12-15, 71-89`**（`CSV_HEADER` / `GOOD_ROWS` /
`bad.write_text(..., encoding="utf-8")` / `refdata.load_standard(bad)`）。
我照 **`test_refdata.py`** 的造法实现了第 10 条测试（`_mini_table` 辅助函数，
3 个档、越小越好、`sprint_50m / male / 大一、大二`）。

**② 计划 Step 1 的测试文件头写了 `import numpy as np`，但 10 条测试没有一条用到它。**
百分位计算发生在生产模块里，测试不需要 numpy。我按简报「**原样**落进」的要求**保留了这一行**，
它现在是死导入（无 linter 配置，`pyproject.toml` 只有 pytest 段，故不会报错）。
若要清掉，是一行删除，但它会偏离「原样」，故留给控制者裁定。

**③ 第 10 条测试我实现得比计划注释更严一点**（计划只要求「断言五档全部落在这 3 个档的得分集合里」）。
实际断言了四件事：五档 ⊆ `{100, 70, 40}`、五档单调不减、`source == "national"` 且 `sample_size == 0`，
**外加**用第二张同阈值但档位分为 `{99, 66, 33}` 的迷你表验证「换表结果随之整体改变、`33 in vals2`」——
这一步是「常模确实只是**注入表**的纯函数、没有回落到真表也没读第二份文件」的**决定性**证据
（33 分在国标里根本不存在，若它悄悄读了真表就不可能出现）。
副作用是它顺带成了第三条方向守卫（变异 A 里它红了）。**没有减少任何计划要求的断言。**

### 关切 7（本轮踩到的写盘事故，记录供后续 Task 防范）— 编辑工具报成功、磁盘上却是旧版本

**原文摘要**：本报告写完后做增量修订时，`SearchReplace` 与随后的整文件 `Write` **都没有落到磁盘**：
两个工具都返回了成功、`Read` 也能读到新内容，但磁盘上始终是第一次 `Write` 的旧版本。

```powershell
$ (Get-Item <report>).Length                          → 42279   （两次编辑后仍与首次写入完全相同）
$ python -c "import os;print(os.stat(<report>).st_size)" → 42279  （用 python 独立 stat 复核，排除 PS 缓存）
$ Select-String -Path <report> -Pattern "关切 7","44806",".gitignore:10" -SimpleMatch
                                                       → 全部 0 命中
$ (Get-Item <report>).LastWriteTime                    → 首次写入的时刻，未被后续两次编辑推进
```

即：`Read` 读到的是编辑器缓冲区，`Get-Item` / `Select-String` / `python os.stat` 读的是磁盘，两者不一致。

**处置**：`Remove-Item <report>` 删掉旧文件（`Test-Path` 复核 → `False`），再按**新文件**路径整文件重写，
然后用 shell 复核字节数与新内容命中数。**本报告即重写后的版本。**

**边界条件值得记准**：同一轮里 `SearchReplace` 对 `backend/app/domain/percentile.py` 的三次变异
**都正常落盘**（每次都有 `Select-String` 的行号+内容证据，且 pytest 真的跑出了变异后的行为），
首次 `Write` 新建 `percentile.py` / `test_percentile.py` / 本报告也都正常落盘。
**失效只发生在「对同一个已存在文件的第二次及以后的整文件写入/增量编辑」上。**

**这正是简报 §0 说的「本项目已因这些吃过 9 次写盘事故」的同类**，且它这次发生在 `.md` 报告上而非源码上。
源码那一侧本轮每次编辑后都做了 `Select-String` 落盘确认，故 `percentile.py` / `test_percentile.py`
的字节可信，`6b68da8` 的内容与本报告引用的实测输出来自同一份磁盘文件
（并用 `git diff --stat` 为空 + SHA256 自洽二次确认）。

**给后续 Task 的教训**：`Select-String` 搜不到「刚写入的独特串」时，不要相信编辑工具的返回值，
**也不要相信 `Read`**——只有 shell（最好再用 `python os.stat` 交叉一次）读到的字节才算数；
对已存在文件的第二次写入若失败，**先删除再按新文件重写**，比重试编辑有效。

## 10. 前向约束

### 给 Task 8（消费 `lookup_p25` / `PercentileRow`）

1. **`p25` 可能是半分，不得假定它是官方档位分。**
   `np.percentile(..., method="linear")` 在离散得分的并列处会插值出 `60.5` 这类值。
   实测 500 人 `2025-2026 week16` 切片的 24 组里有 **1 组**是半分
   （`standing_jump / female / 大三、大四 = 60.5`）。
   任何「`p25` 必然 ∈ 官方档位分集合」的断言或对账都会翻车。
2. **短板判定必须用严格小于 `score < p25`（spec §14 #21），且要知道它的后果。**
   就低取档使每项得分只有 ≤20 个离散取值（男引体向上仅 15 个），P25 处并列质量很高：
   若某组 30% 的人同为 60 分且 P25 恰为 60，这 30% **全都不算**短板。
   这是刻意口径、不是缺陷，已写在 `compute_snapshot` 与 `lookup_p25` 两处 docstring。
   `find_weaknesses` **不得**自行改成 `<=`——那会实质改变 `W`、改变红黄绿比例、
   甚至改变 `valid_count >= 4` 闸门的通过情况。
3. **`lookup_p25` 返回 `None` 表示「这一组没有判定线」，与「判定线是 0 分」是两件事。**
   `None` 时该项必须**不计入 `W`**（等同缺测，绝不当 0 分，也绝不当「不短板」而静默跳过统计），
   并且要影响 `valid_count`。这与 spec §6.3① / Review Focus #2「缺失项绝不当 0 分」是同一条纪律，
   已写在 `lookup_p25` 的 docstring。
4. **`source` 只有两种取值：`"school"` 与 `"national"`**，与 ORM
   `PercentileSnapshot.SOURCES`（`models.py:360`）同域，且受 CHECK 约束
   `ck_percentile_snapshot_source` 保护。Task 8 若要按来源分别处理（例如降级组的短板不计入某个统计），
   判据是 `row.source == "national"`，**不要**用 `row.sample_size < 30` 去反推——见下一条。
5. **`sample_size` 有两种含义，不能当同一种量用。**
   `source == "national"` 且来自 `national_norm` 直接调用时是 **`0`**，含义是「无样本、纯推导」；
   而 `compute_snapshot` 降级产出的行是**真实观测人数**（1..29），
   因为 Review Focus #4 要求留痕。所以「`sample_size == 0` ⇒ 降级行」**不成立**；
   **唯一可靠的判据是 `source`**。这一点在 `PercentileRow` / `national_norm` / `compute_snapshot`
   三处 docstring 都写了（简报 §3 Step 1 的明确要求）。
6. **降级行除 `sample_size` 外逐字段等于 `national_norm` 的产出**，且这是用
   `dataclasses.replace(national_norm(...), sample_size=len(group))` **机械保证**的，
   不是手抄五个字段——Task 8 因此可以放心地拿
   `national_norm(table, item, sex, age_group)` 当降级行的参照值对账。
7. **`compute_snapshot` 的返回顺序是规范序**：按 `(item.value, sex.value, age_group)` 排序，
   **不依赖调用方拼装 `scores` 的顺序**。Task 8 / Task 10 可以直接逐行对比两次运行的输出。
   （这是本轮加的一条确定性保证，计划未要求；若控制者认为超范围，删掉
   `percentile.py` 末尾那一行 `snapshot.sort(...)` 即可，10 条测试无一依赖行序。）
8. **`sex` / `item` 在 `PercentileRow` 里是枚举成员，不是裸字符串**：
   `compute_snapshot` 用 `Sex(row["sex"])` / `ScoredItem(row["item"])` 归一化，
   非法值会当场 `ValueError`（响亮失败，不静默另立孤儿组）。
   因为两者都是 `str` 枚举，`row.sex == "male"` 与 `row.sex == Sex.MALE` 都为真，
   `lookup_p25` 传枚举或传裸字符串都能命中。
9. **`compute_snapshot` 不按 `student_id` 去重**（关切 3）。Task 8 若从未经清洗的路径取数，
   重复记录会被当作独立样本。生产路径上 Task 5 清洗层负责去重。
10. **`table` 必须由调用方注入**（Ruling 87）。Task 8 若需要 `national_norm`，
    同样要接收 `table` 参数，**不得**在 `app/domain/` 里 import `app.refdata`。
11. **`PERCENTILES` 是五档的唯一声明处**：字段名由 `_PERCENTILE_FIELDS` 从它生成、
    经 `_percentile_fields()` 摊成关键字构造 `PercentileRow`。加一档而忘了加字段（或反过来）
    会在构造时当场 `TypeError`，不会静默少算一档。Task 8 若要读 P20（体成分 `C` 的肌肉量判定线，
    spec §6.3②），字段就是 `row.p20`，已在本轮产出里。

### 给 Task 10（物化落库）

1. **要补的三个列**：`semester_id`、`computed_on`、`batch_id`。
   `PercentileRow` **刻意不含**这三个字段（Ruling 86）——它们属于「哪一次运行」而不是「这一组的分布」，
   由 Task 10 在写 `PercentileSnapshot` 时补，它本来就握着业务日期（幂等键
   `(semester_id, business_date)` 的一半）。`compute_snapshot(scores, table)` 的签名里
   **没有也不该有** `computed_on`。
2. **其余 10 个业务列一一对应**：`item` / `sex` / `age_group` / `p10` / `p20` / `p25` / `p50` / `p75` /
   `sample_size` / `source`（`models.py:368-377`）。
   `item` 与 `sex` 落库时要取 `.value`（ORM 列是 `String(32)` / `String(8)`）。
3. **五列业务唯一键**是 `UniqueConstraint("semester_id", "computed_on", "item", "sex", "age_group")`
   （`uq_percentile_snapshot_group_day`，`models.py:382-389`），正是本轮分组键
   `(sex, age_group, item)` 加「哪个学期、哪一天」。
   `compute_snapshot` **对每个分组只产出一行**（样本 < 30 时整组降级为 `source = "national"`，
   不是「校内行 + 常模行」并存两行），故 `source` 不必进键、也不会撞唯一约束。
4. **`sample_size` 在降级行是真实观测人数**，直接落库即满足 Review Focus #4 的留痕要求，
   不需要另加标记列；`source = "national"` 就是标记（ORM 的 CHECK 约束会拦非法值）。
5. **`batch_id` + `delete_by_batch`** 是本表的幂等防线（Ruling 29，`models.py:347-350` 的 docstring）。
   重放同一业务日期时先按 `batch_id` 删再插，或直接依赖上面的唯一键。
6. **喂给 `compute_snapshot` 的必须是清洗后的数据**：本模块不去重、不夹取物理不可能值、
   不处理量纲错误（那是 Task 5 的职责）。关切 3 已实测重复记录会被当作独立样本。
7. **本轮零改动 `backend/app/seed/` 与 `backend/data/`**，Task 10 若要跑 500 人端到端，
   三个 CSV 的哈希与 Task 6 结案时一致（§5 的 `git diff --stat` 证明）。
8. **不得创建 `backend/pe.db` 以外的库文件、不得往 `backend/data/seed/` 写东西**（Ruling 68 及本轮纪律）；
   `backend/data/seed/` 现在是空目录，本轮结束时仍为空。

### 给 spec 维护者

- §14 **#24** 那句「实测 24 组逆序 0 组、国标 P25 落在 **40–64**，与 500 人仿真数据的本校 P25（**50–62**）同量级」
  需要两处更正：**40 → 30**（关切 1）、**50–62 补切片条件或改为跨切片全距 40–64**（关切 2）；
  并建议按关切 4 补写降级后的偏差幅度与方向。**本轮未改 spec。**

---

## 11. 交付物清单与临时文件复核

| 交付物 | 状态 |
|---|---|
| `backend/app/domain/percentile.py`（新建） | ✅ 已提交于 `6b68da8` |
| `backend/tests/domain/test_percentile.py`（新建，10 条测试） | ✅ 已提交于 `6b68da8` |
| 本报告 `.superpowers/sdd/.../task-7-report.md` | ✅ 本文件（`.superpowers/` 被 `.gitignore:10` 忽略，故不进 commit） |
| `backend/data/national_norm.csv` | ❌ **未创建**（Ruling 84 已取消；本轮零新增数据文件） |
| `backend/pe.db` | ❌ **未创建、未触碰**（`Test-Path` → `False`，Ruling 68） |
| `backend/data/seed/` | 仍为**空目录**（`Get-ChildItem -Force` → Count 0） |
| `backend/app/seed/` | **零改动**（`git diff --stat c72b53f..HEAD -- backend/app/seed/` 为空） |
| `app/domain/indicators.py` | **零改动**（本轮未动 Task 6 加的 `ITEM_WEIGHTS`） |

临时探针（全部写在 `%TEMP%`，**不在仓库内**）与删除复核：

```
$ Remove-Item $env:TEMP\task7_probe.py, $env:TEMP\task7_probe_out.txt, `
              $env:TEMP\task7_probe2.py, $env:TEMP\task7_probe2_out.txt -Force

$ foreach ($f in "task7_probe.py","task7_probe_out.txt","task7_probe2.py",
                 "task7_probe2_out.txt","task7_commitmsg.txt") {
      "$f = $(Test-Path (Join-Path $env:TEMP $f))" }
task7_probe.py         = False
task7_probe_out.txt    = False
task7_probe2.py        = False
task7_probe2_out.txt   = False
task7_commitmsg.txt    = False      （提交时即删，此处再确认）
```

**5 个临时文件逐个 `Test-Path` 全为 `False`**，仓库内零残留。

报告自身存在且非空的复核（`Write` 重写后由 shell 实测；把实测数字再写回文件本身会让字节数变化几字节，
故报告内不嵌自指数字，实测值见控制者收到的返回消息）：

```
$ (Get-Item ".superpowers\sdd\2026-09-28-实施计划01-数据基座与分层引擎\task-7-report.md").Length
→ 非零（>40 KB）；并用 Select-String 确认「关切 7」「.gitignore:10」等新写入的独特串各命中 >= 1 次
```

---

## 12. 文末状态复核

```
$ git log --oneline -1
6b68da8 feat: 校内同龄同性别百分位快照，样本不足30人降级为按评分表推导的国标常模并留痕

$ git status --short
(无输出 —— 工作树干净)
```

`git status --short` 为空的原因值得记一句：本报告所在的 `.superpowers/` 已被
`.gitignore:10` 忽略（`git check-ignore -v` 实测命中该行），故报告落盘**不会**弄脏工作树，
`6b68da8` 是本轮**唯一**一个 commit，且只含两个源文件。

三次变异全部还原后，`backend/app/domain/percentile.py` 与 `6b68da8` 里的版本
**零字节差异**（`git diff --stat` 为空 + SHA256 `C4E8A1EE…048AC5` 在三次还原间自洽 +
三个变异标记各 0 命中），全量测试 **328 passed**、`-W error` **328 passed**。

---

## Fix Round 1

**裁定范围**：Ruling 88（`compute_snapshot` 的 `scores` 契约删掉从不消费的 `student_id`，并在同处 docstring 补写「调用方职责」）＋ Ruling 89（测试文件删掉死导入 `import numpy as np`）。

**基线 → 本轮**：`627cd16`（工作树干净）→ **本轮唯一 commit `bb97c82`**。分支 `feature/plan-01-data-foundation`，未 rebase、未 reset、未 force push、未切分支。

**性质**：**纯文档/契约改动**。零逻辑变更、零函数签名变更、零新增运行时校验或断言、零测试增删、既有断言**一条未改**。commit type 因此用 `docs` 而非 `fix`。

### R1.1 测试数与洁净度（328 → 328）

| 时点 | 命令（均在 `backend/` 下执行，无 venv） | 结果 |
|---|---|---|
| 改动前 `627cd16` | `pytest -q -W error` | **328 passed in 9.69s** |
| 改动后 `bb97c82` | `pytest -q -W error` | **328 passed in 10.21s** |

```
$ cd backend; pytest -q -W error
........................................................................ [ 21%]
........................................................................ [ 43%]
........................................................................ [ 65%]
........................................................................ [ 87%]
........................................                                 [100%]
328 passed in 10.21s
```

- 测试数**不增不减**：328 → 328，符合本轮「不增不减测试」的硬约束。
- `-W error` **洁净**：无 warning 被升级为 error，输出里**没有** `warnings summary` 段落。
  删掉 `import numpy as np` 之后仍洁净，说明该 import 既未被使用、也未触发任何导入期警告。
- `tests/domain/test_percentile.py` 仍是 **10 条**测试，文件行数 111 → **110**（只少了那一行 import）。

### R1.2 两处改动的前后对照与行号

#### 改动一：Ruling 88 —— `backend/app/domain/percentile.py`

`git diff --numstat`：**20 insertions / 1 deletion**（唯一的 1 处删除就是契约行本身，其余 20 行全是新增 docstring 正文）。

契约行（**`:155`**，改动前后同一行号）：

```diff
     ``scores`` 每项形如
-    ``{"student_id": int, "sex": str, "age_group": str, "item": ScoredItem, "score": int}``，
+    ``{"sex": str, "age_group": str, "item": ScoredItem, "score": int}``，
     其中 ``score`` **必须已经是 :func:`~app.domain.indicators.score_item` 正查出来的
```

新增的「调用方职责」三段（**`:162-179`**，插在契约段与「五档用 `np.percentile`」段之间）：

```diff
     ``source = "national"``，不是「校内行 + 常模行」并存两行。
 
+    **调用方职责：每个 (学生, 项目) 组合只能出现一行。** 本函数逐行收样本，同一学生在
+    同一项目上出现两行就会被当成**两个独立样本**计入分位数，把 P25 拉向重复值那一侧——
+    而 P25 正是 spec §6.3① 里短板判定 ``W`` 的唯一判定线，「谁被标为短板」于是随重复行
+    一起漂移，且全程不报错。生产路径上这道去重由 **Task 5 的清洗层**负责：体测按
+    ``(student_no, batch_key)``、体成分按 ``(student_no, measured_on)`` 去重，各自保留
+    输入顺序中靠后的一行（见 :mod:`app.pipeline.clean`）。
+
+    :func:`compute_snapshot` **刻意不做第二道去重**，两个理由：① 它是 domain 层的内部
+    边界而不是系统入口，重复校验属于上游职责，在这里再查一遍只会让「去重的所有者是谁」
+    变得含糊；② 更要紧的是**静默去重会掩盖上游去重失效**——那正是本项目反复吃亏的缺陷
+    形态：一处代码把另一处的错误悄悄吸收掉，测试全绿、日志无异常，直到结论错了才暴露。
+    宁可让重复样本如实体现在分位数上，也不要让它消失在第二次去重里。
+
+    契约里**没有** ``student_id``。调用方传入多余的键（例如它手里的 ORM 行本来就带着
+    ``student_id``）**不会被拒绝**，只是不被消费：分组只读 ``sex`` / ``age_group`` /
+    ``item``，百分位只读 ``score``。Ruling 88 把它从契约里删掉，与 Ruling 86 删掉
+    ``computed_on`` 参数同理——**一个被接收然后被丢弃的字段是撒谎**，列在契约里会让人
+    以为它参与了去重或留痕。
+
     五档用 ``np.percentile(..., method="linear")``，档位一律取自 :data:`PERCENTILES`。
```

简报要求的四个要点逐条落位：

| 要点 | 落位 |
|---|---|
| 每个 `(学生, 项目)` 只能一行；重复行被当独立样本，把 P25 拉向重复值那一侧 | `:162-165` |
| 生产路径由 Task 5 清洗去重保证（两个去重键 + 见 `app/pipeline/clean.py`） | `:165-167` |
| 刻意不做第二道去重的两个理由（内部边界非入口 / 静默去重掩盖上游失效） | `:169-173` |
| 多余键不被拒绝、只是不被消费；契约不列出它以免暗示它有用 | `:175-179` |

⚠️ **去重键按生产代码的真实值写，未按简报原文照抄** —— 简报写的是「体测去重键 `(student_no, tested_on)`」，而 `app/pipeline/clean.py` 的实际键是 `(student_no, batch_key)`。详见 **R1.6 关切 1**。

未改动的部分（明确核对）：`compute_snapshot` 签名 `:149-151` 原样、函数体 `:182-211`（改动后 `:201-230`）**零字节变更**、`national_norm` 与模块级 docstring 原样、无新增 `assert` / `if` / 校验分支。

#### 改动二：Ruling 89 —— `backend/tests/domain/test_percentile.py`

`git diff --numstat`：**0 insertions / 1 deletion**（纯删一行，无其它字节变动）。

```diff
 """校内百分位快照的行为约束：分组键、五档口径、样本不足降级国标常模（Review Focus #4）。"""
-import numpy as np
 from app.domain.percentile import (
     MIN_SAMPLE, PERCENTILES, compute_snapshot, lookup_p25, national_norm,
 )
```

删前已按简报要求**自行核实**：`np.` 在该文件 **0 命中**（见 R1.3）。核实为 0 命中，故执行删除；若当时有命中就会停下来上报。

### R1.3 `Select-String` 证据

**证据 A —— `percentile.py` 里 `student_id` 现在只出现在新写的「调用方职责」docstring 里**（即它作为**契约键**已消失）：

```
$ cd backend
$ Select-String -Path app\domain\percentile.py -Pattern "student_id" | Select-Object LineNumber

LineNumber
----------
       175
       176
```

两行都在 R1.2 新增的第三段里（`:175` = 「契约里**没有** `student_id`。」，`:176` = 「``student_id``）**不会被拒绝**，只是不被消费」）——都是在**声明它不在契约中**，而不是把它列为契约键。改动前该模式命中的是**单行 `:155`**（契约字典字面量里），现在 `:155` 已无命中。对基线 commit 取同一证据（管道输入时 `Select-String` 的默认输出不带行号，故用 `ForEach-Object` 显式打出行号）：

```
$ git show 627cd16:backend/app/domain/percentile.py | Select-String -Pattern "student_id" | ForEach-Object { "L" + $_.LineNumber }
L155

$ git show 627cd16:backend/app/domain/percentile.py | Select-String -Pattern "student_id" | ForEach-Object { $_.Line }
    ``{"student_id": int, "sex": str, "age_group": str, "item": ScoredItem, "score": int}``，
```

即：基线上 `student_id` **仅 `:155` 一处**（与控制者的预检一致，我自己复核过），且那一处就是契约字典字面量；改动后它从契约里消失，只剩 `:175` / `:176` 两处「声明它不在契约中」的正文。

**证据 B —— `test_percentile.py` 里 `np.` 为 0 命中**（删前与删后都是 0，删前 0 命中正是「可以安全删」的判据）：

```
$ Write-Output ("numpy_hits=" + (Select-String -Path tests\domain\test_percentile.py -Pattern "numpy").Count)
$ Write-Output ("np_dot_hits=" + (Select-String -Path tests\domain\test_percentile.py -Pattern "np\.").Count)
numpy_hits=0
np_dot_hits=0
```

删后 `numpy` 也是 0 命中，说明整条依赖声明已从文件里消失（不只是「不用了但还挂着」）。

⚠️ **取证方法上的一个坑，已记为 R1.6 关切 2**：`Select-String` 的命令里**含中文模式**时，整条命令行会被静默打乱，连同一条命令里的 ASCII 模式一起返回 0 命中（假阴性）。上面两条证据都刻意只用 **ASCII 模式**；涉及中文内容的核对一律改用 python 读字节。

中文内容用 python 独立复核（与证据 A 自洽）：

```
$ python -c "t=open('app/domain/percentile.py','rb').read().decode('utf-8'); print(t.count('student_id'))"
2
```

### R1.4 `git diff --stat` 证据

**全量（`627cd16..HEAD`）—— 只有那两个文件**：

```
$ git diff --stat 627cd16..HEAD
 backend/app/domain/percentile.py        | 21 ++++++++++++++++++++-
 backend/tests/domain/test_percentile.py |  1 -
 2 files changed, 20 insertions(+), 2 deletions(-)

$ git diff --name-only 627cd16..HEAD
backend/app/domain/percentile.py
backend/tests/domain/test_percentile.py
```

**`backend/app/seed/` 定向 —— 为空**（Task 6 三个 CSV 的哈希因此不受影响）：

```
$ git diff --stat 627cd16..HEAD -- backend/app/seed/
(无输出)

$ Write-Output ("seed_stat_empty=" + ((git diff --stat 627cd16..HEAD -- backend/app/seed/) -eq $null))
seed_stat_empty=True
```

附带核对的其它禁区（本轮全部未触碰）：

```
$ Write-Output ("pe_db_exists=" + (Test-Path pe.db))
pe_db_exists=False                       # 未创建、未触碰 backend/pe.db（Ruling 68）

$ Write-Output ("data_seed_children=" + (Get-ChildItem data\seed -Force | Measure-Object).Count)
data_seed_children=0                     # backend/data/seed/ 仍是空目录

$ Test-Path data\national_norm.csv
False                                    # Ruling 84 已取消，本轮未创建任何数据文件
```

未动的文件（简报点名清单）：`app/domain/indicators.py`、`app/refdata.py`、`app/db/`、`app/pipeline/`、`app/seed/`、`app/adapters/` —— 均不在 `git diff --name-only` 的输出里。Task 8 的任何东西（`find_weaknesses` / `classify_trend` / `national_total` / `derive`）**未实现**。

### R1.5 落盘复核（上一轮写盘事故的判据：`Get-Item.Length` ＋ `LastWriteTime`，不看工具返回值、不看 `Read` 结果）

两个文件都是**已存在文件的第二次写入**，正是事故触发条件，故每处改完立刻用 shell 复核。

| 文件 | Length 前 | Length 后 | 差值 | 与预期一致？ | LastWriteTime 前 | LastWriteTime 后 | 推进？ |
|---|---|---|---|---|---|---|---|
| `backend/app/domain/percentile.py` | **13405** | **15127** | **+1722** | ✅ 新增 19 行中文 docstring（约 570 个中文字符 × 3 字节 UTF-8 ≈ 1710）＋契约行变短 | `2026/9/30 5:17:26` | `2026/9/30 5:45:13` | ✅ **已推进** |
| `backend/tests/domain/test_percentile.py` | **5970** | **5951** | **−19** | ✅ 恰等于 `import numpy as np` ＋ 换行符的字节数（18 + 1） | `2026/9/30 5:06:48` | `2026/9/30 5:46:07` | ✅ **已推进** |

```
$ Get-Item app\domain\percentile.py | Select-Object Length,LastWriteTime
Length LastWriteTime
------ -------------
 15127 2026/9/30 5:45:13

$ Get-Item tests\domain\test_percentile.py | Select-Object Length,LastWriteTime
Length LastWriteTime
------ -------------
  5951 2026/9/30 5:46:07
```

**结论：本轮两次写入都真实落盘，未触发写盘事故，无需 `Remove-Item` 重写。**

三重交叉验证（排除「Length 变了但内容是旧的」这种更隐蔽的形态）：

1. `Get-Item.Length` 前后值如上，均按预期方向变化（一个增、一个减），且减幅**精确等于**被删行的字节数 —— 说明是**定点删除**而非整文件重写。
2. `git diff --numstat` = `20 / 1` 与 `0 / 1`，与 Length 变化互相印证；若曾整文件重写，numstat 会显示上百行增删。
3. python 直接读磁盘字节复核编码与内容：
   ```
   $ python -c "b=open('app/domain/percentile.py','rb').read(); print(len(b), b[:3]==b'\xef\xbb\xbf', b.decode('utf-8').count('student_id'), b.count(b'\n'))"
   15127 False 2 255
   ```
   即：磁盘上 15127 字节、**无 BOM**（未被写成 UTF-8-BOM）、UTF-8 可完整解码、`student_id` 2 处、255 行（= 236 + 19）。行数与新增行数自洽。

文件编码与行尾**均未被本轮编辑改变**：`percentile.py` 仍为 CRLF（255/255）、`test_percentile.py` 仍为 bare LF（110 行，0 个 CRLF），与改动前一致。

### R1.6 关切

> 每条都附**可复现的测量方法**，并注明该方法读的是**生产代码的中间状态**还是**我自己重新推导的输入**。

#### 关切 1（高，**简报的事实错误**）：简报给的体测去重键 `(student_no, tested_on)` 与生产代码不符，真实键是 `(student_no, batch_key)`

简报原文要求 docstring 写「生产路径由 Task 5 的清洗去重保证（体测去重键 `(student_no, tested_on)`、体成分 `(student_no, measured_on)`，见 `app/pipeline/clean.py`）」。但简报同时把我指向了 `clean.py`，而 `clean.py` 里体测的键**不是** `tested_on`：

```
$ cd backend
$ Select-String -Path app\pipeline\clean.py -Pattern "key_of=lambda" | ForEach-Object { "L" + $_.LineNumber + ": " + $_.Line.Trim() }
L313: key_of=lambda r: (r.student_no, r.batch_key),
L372: key_of=lambda r: (r.student_no, r.measured_on),
```

`:313` 是 `clean_fitness`（体测）→ 键为 `(student_no, batch_key)`；`:372` 是 `clean_body_comp`（体成分）→ 键为 `(student_no, measured_on)`，这一半简报是对的。`clean.py` 自己的两处 docstring 也一致这么写：

```
$ Select-String -Path app\pipeline\clean.py -Pattern "batch_key" | ForEach-Object { "L" + $_.LineNumber }
L26
L71
L297
L303
L313
L321
L411
```

其中两处是**明文陈述去重键**的 docstring（其余是 `_IDENTITY_FIELDS` 常量、`key_of` 本体与审计文案）：

- `:26`（模块级 docstring）：「两类记录都去重（体测按 ``(student_no, batch_key)``、体成分按 ``(student_no, measured_on)``）并保留输入顺序中靠后的一行」
- `:303`（`clean_fitness` docstring）：「去重键是 ``(student_no, batch_key)``，**保留输入顺序中靠后的那一条**」

`batch_key` 的形状由 `app/adapters/base.py:39` 定义：形如 `"<academic_year>|<timepoint>"`，只由 `parse_batch_key` / `make_batch_key` 读写（Ruling 35）。

**我的处置**：docstring 按**生产代码的真实键**写（`percentile.py:166`），没有照抄简报。**理由**：这段文字显式引用 `app.pipeline.clean` 作为出处，若写 `tested_on`，`percentile.py` 就会与它引用的模块直接矛盾 —— 那正是本轮两条裁定要消灭的缺陷形态（一处文字对读者撒谎），而且这次是**新增**的谎。两个键的差异不是措辞问题而是**语义问题**：`(student_no, batch_key)` 意味着「同一学生在同一学年同一时间点只保留一条」，同一学生在 `week1` 与 `week16` 各有一条是**合法的**；而 `(student_no, tested_on)` 会允许同一批次内不同日期的两条都留下。对 `compute_snapshot` 的调用方来说，这直接决定了「哪些行必须由调用方自己合并」。

**疑似笔误来源**：`tested_on` 在 `clean.py:317-323` 里确实高频出现，但它是去重条目里被**记录/对比的值**（`original_value=discarded.tested_on`、`processed_value=kept.tested_on`）与审计文案的一部分，**不是键的一半**。

- **测量方法读的是什么**：`clean.py` / `base.py` 是**已结案的生产代码（Task 5 / Task 3）的当前磁盘状态**，不是我推导的输入；上面的行号与内容可直接复现。
- **建议**：若控制者认可，`percentile.py:166` 保持现状即可（已是正确值）；无需回改。

#### 关切 2（中，**取证工具的假阴性**）：`Select-String` 命令里含中文模式会静默返回 0 命中，并连带废掉同一条命令里的 ASCII 模式

本轮实测：改完 `percentile.py` 后我执行了一条组合命令，模式一是中文串、模式二是 `student_id`，**两者都无输出**：

```
$ Select-String -Path $p -Pattern "调用方职责：每个 (学生, 项目) 组合只能出现一行" -SimpleMatch | Select-Object LineNumber
$ Select-String -Path $p -Pattern "student_id" -SimpleMatch | Select-Object LineNumber
(两条都无输出)
```

但同一时刻 `percentile.py` 磁盘上确实有 2 处 `student_id`（python 读字节 = 2，`git diff` 也显示新增段落含该串）。把中文模式去掉、只留 ASCII 模式后立刻正常：

```
$ Select-String -Path app\domain\percentile.py -Pattern "student_id" | Select-Object LineNumber
175
176
```

**推断**：含中文的命令行在传给 PowerShell 时编码被破坏，中文串里的字节打断了引号配对，导致其后的命令一起被吞掉 —— 表现为**整条命令静默无输出**，而不是报错。

**为什么这条值得上报**：它是本项目反复吃亏的形态的**工具层版本** —— 一个假阴性被静默吸收，全程不报错。具体危害有两个方向：
- 用它验证「某串**应该已经消失**」→ 得到碰巧正确但**依据错误**的结论（本轮若只看这条输出，我会以为 `student_id` 已从 `percentile.py` 全文消失，包括我新写的那段）；
- 用它验证「某串**应该存在**」→ 误判为**写盘事故**，进而触发「`Remove-Item` 后按新文件重写」这条昂贵且有风险的补救路径。

**纪律建议**：`Select-String` 只用 **ASCII 模式**；凡涉及中文内容的核对，一律用 python 读字节（`open(p,'rb').read().decode('utf-8').count(...)`）或 `git diff` 交叉验证。本轮 R1.3 / R1.5 的所有证据都遵守了这一点。

- **测量方法读的是什么**：读的是**工具行为本身**（同一条命令在含/不含中文模式时的输出差异），与生产代码状态无关，可原样复现。

#### 关切 3（低，范围外但值得知道）：测试的 `rows()` 助手仍在每行里带 `student_id`，而它现在是一个「无断言覆盖的契约声明」

```
$ Select-String -Path tests\domain\test_percentile.py -Pattern "student_id"
tests\domain\test_percentile.py:17:    return [{"student_id": start + i, "sex": sex, "age_group": age_group,
```

（改动前这一行是 `:18`，删掉 import 后整体上移一行。）`rows()` 是本文件**唯一**构造 `scores` 的助手，5 条 `compute_snapshot` 测试全部用它。改动后这个键**不再出现在契约里**，但它仍被传入 —— 这恰好是新 docstring `:175-176` 那句「多余的键不会被拒绝，只是不被消费」的**活体证据**：这 5 条测试全绿（328 passed）本身就证明了「传多余键不报错」。

**我没有改它**，因为简报本轮只授权删 `import numpy as np` 一行，且改了会让「多余键不被拒绝」失去唯一的实测覆盖。**但需要指出**：这条声明目前是靠**巧合**被覆盖的（测试数据碰巧带了个多余键），而不是靠一条**指名道姓的断言**。将来任何人把 `rows()` 里的 `student_id` 清掉，`compute_snapshot` 对多余键的容忍度就**再无任何测试保护**，而 docstring 里那句话仍然写着。

- **测量方法读的是什么**：`test_percentile.py` 是**生产测试代码的当前磁盘状态**；「10 条测试全绿 ⇒ 多余键不被拒绝」这个推论的依据是**本轮实跑的 `pytest -q -W error`（328 passed）**，不是我重新构造的输入。
- **建议（若控制者要开下一轮）**：加一条 2 行测试，显式断言「带未知键的一行能被正常消费」，把这条声明从巧合升格为契约测试。**本轮未做**（超出授权范围）。

#### 关切 4（低，既有状态）：`test_percentile.py` 是全 bare LF，在 `core.autocrlf=true` 下每次 git 操作都打印 CRLF 警告

```
$ python -c "for p in ('app/domain/percentile.py','tests/domain/test_percentile.py'):
    b=open(p,'rb').read(); print(p,'CRLF',b.count(b'\r\n'),'bare_LF',b.count(b'\n')-b.count(b'\r\n'))"
app/domain/percentile.py CRLF 255 bare_LF 0
tests/domain/test_percentile.py CRLF 0 bare_LF 110

$ git config core.autocrlf
true
```

于是本轮每次 `git add` / `git diff` / `git commit` 都打印：
`warning: in the working copy of 'backend/tests/domain/test_percentile.py', LF will be replaced by CRLF the next time Git touches it`

**这是既有状态，不是我引入的**，有两项证据：① 该文件由上一轮（`6b68da8`）以 LF 创建；② 本轮对它的 `git diff --numstat` 是 `0 insertions / 1 deletion`，Length 精确 −19 字节 —— 字节级只少了那一行，行尾未被触碰（若我做了行尾转换，numstat 会是 `110 / 111` 这种整文件增删）。

**为什么仍值得记一句**：将来任何人对该文件跑 `git add --renormalize`（或用会改写行尾的编辑器保存一次），就会产出一个**整文件 diff**，把 `git diff --stat` / `--numstat` 这类**本项目当作落盘与范围证据使用**的输出全部污染成噪音 —— 而本项目已连续多轮用 numstat 判定「有没有偷偷改别的文件」。

- **测量方法读的是什么**：读的是**工作树文件的原始字节**与 `git config` 的当前值，均为可直接复现的现状，不含推导。
- **建议**：不在本轮处理。若要根治，宜在全仓统一（`.gitattributes` 里给 `*.py` 定 `eol`），单独一轮做，别混进任何功能性 commit。

### R1.7 前向约束

**无新增，沿用上一轮的清单**（见本报告 §10：给 Task 8 的 11 条、给 Task 10 的 8 条、给 spec 维护者的 1 条）。本轮是纯文档改动，没有引入任何新的行为约束。

但上一轮清单里有**两条的措辞现在需要微调**，因为它们引用的键名已随 Ruling 88 从契约里消失：

| 上一轮原文 | 建议措辞 | 原因 |
|---|---|---|
| 给 Task 8 **#9**：「`compute_snapshot` **不按 `student_id` 去重**。Task 8 若从未经清洗的路径取数，重复记录会被当作独立样本。」 | 「`compute_snapshot` **不按 `(学生, 项目)` 去重**（它根本不看身份列 —— 契约里没有 `student_id`）。Task 8 若从未经清洗的路径取数，重复记录会被当作独立样本。」 | `student_id` 已不是契约的一部分，继续用「不按 `student_id` 去重」描述会让人以为函数**收**这个键只是**不用它去重**；实际是**契约里就没有它**，传进来也只是被忽略的多余键。 |
| 给 Task 10 **#6**：「喂给 `compute_snapshot` 的必须是清洗后的数据：本模块不去重……」 | 同上，并补一句去重键的**真实值**：体测 `(student_no, batch_key)`、体成分 `(student_no, measured_on)` | 见 **关切 1** —— Task 10 拼装 `scores` 时若要跨批次合并同一学生的多次测量，判断「哪些行算重复」的依据是 `batch_key` 而不是 `tested_on`，两者语义不同。 |

这两条只是**报告文字**的建议，**本轮未回改 §10**（简报要求只追加、不重写既有内容）。生产代码里的对应文字（`percentile.py:162-179`）已按正确口径写好，故 Task 8 / Task 10 的实现者只要读 docstring 就不会被 §10 的旧措辞误导。

### R1.8 本轮交付物与临时文件复核

| 交付物 | 状态 |
|---|---|
| commit `bb97c82`（`docs:` 类型，本轮**唯一** commit） | ✅ 只含 `backend/app/domain/percentile.py` ＋ `backend/tests/domain/test_percentile.py` |
| `backend/app/domain/percentile.py` | ✅ 契约行 `:155` 改定，新增 `:162-179`（+20 / −1） |
| `backend/tests/domain/test_percentile.py` | ✅ 删掉 `import numpy as np`（+0 / −1），10 条测试一条未改 |
| 本报告 `## Fix Round 1` 章节 | ✅ **追加**于文件末尾，既有 12 个章节零改动 |
| `backend/pe.db` | ❌ 未创建、未触碰（`Test-Path` → `False`） |
| `backend/data/seed/` | 仍为**空目录**（`Get-ChildItem -Force` → Count 0） |
| `backend/data/national_norm.csv` | ❌ 未创建（Ruling 84） |
| `backend/app/seed/` | **零改动**（`git diff --stat 627cd16..HEAD -- backend/app/seed/` 为空） |
| Task 8 的任何实现 | ❌ 未做（`find_weaknesses` / `classify_trend` / `national_total` / `derive` 一个都没碰） |

临时文件（本轮只用了 1 个，写在 `%TEMP%`，**不在仓库内**）与删除复核：见本章末尾「文末状态复核」。

### R1.9 文末状态复核

```
$ git log --oneline -1
bb97c82 docs: scores 契约删掉从不消费的 student_id，测试删掉死导入 numpy

$ git status --short
(无输出 —— 工作树干净)
```

`git status --short` 为空的原因与上一轮相同：本报告所在的 `.superpowers/` 被 `.gitignore` 忽略，故追加报告**不会**弄脏工作树；`bb97c82` 是本轮**唯一**一个 commit，且只含两个源文件。

**临时文件清单与删除复核**（补 R1.8 的指针：本轮共用 3 个临时文件，全部写在 `%TEMP%`，**没有一个落在仓库内**）：

| # | 临时文件 | 用途 | 存在期 |
|---|---|---|---|
| 1 | `%TEMP%\task7_fixround1_section.md` | 承载本章正文（25123 字节），按**新文件**写出以规避「已存在文件二次写入」的事故条件 | 已删 |
| 2 | `%TEMP%\task7_append_report.py` | 校验 1 号文件的 3 处订正是否真落盘（5 条 must_have ＋ 4 条 must_not），再以**二进制追加**方式把 1 号文件接到本报告末尾 | 已删 |
| 3 | `%TEMP%\task7_fixround1_tail.md` | 承载本段（临时文件清单） | 追加后立即删 |

```
$ Remove-Item "$env:TEMP\task7_fixround1_section.md","$env:TEMP\task7_append_report.py" -Force
$ Write-Output ("section_md_exists=" + (Test-Path "$env:TEMP\task7_fixround1_section.md"))
$ Write-Output ("append_py_exists=" + (Test-Path "$env:TEMP\task7_append_report.py"))
section_md_exists=False
append_py_exists=False
```

**报告确实变长（`Get-Item.Length`）**：

```
$ Get-Item <report> | Select-Object Length,LastWriteTime     # 追加前
Length LastWriteTime
------ -------------
 46805 2026/9/30 5:35:44

$ Get-Item <report> | Select-Object Length,LastWriteTime     # 追加后
Length LastWriteTime
------ -------------
 71928 2026/9/30 5:55:22
```

46805 → **71928**（+25123 字节，恰等于 1 号临时文件的字节数），LastWriteTime 由 `5:35:44` 推进到 `5:55:22`。

**是「只追加、没有重写整个文件」的字节级证明**（这是本轮对报告文件的硬约束）：

```
prefix_intact True        # 追加后文件的前 46805 字节与追加前逐字节相同
bom False                 # 未被写成 UTF-8-BOM
h2_count 13               # 既有 12 个 `## ` 章节一个不少，末尾多出 `## Fix Round 1`
fixround1_count 2         # 一次是章节标题，一次是 R1.8 交付物表里的引用
```

`prefix_intact` 由 2 号脚本在写入后立即计算（`after[:len(before)] == before`），排除「报告被整文件重写、既有 46805 字节被悄悄改动」这种形态 —— 上一轮 11 次写盘事故的判据同样适用于这里。

追加采用**二进制模式**（`open(REPORT, "ab")`）而非 PowerShell 的 `Add-Content`：后者在 PowerShell 5.1 下默认按 ANSI 编码写入，会把中文正文变成乱码，且**不报错**（又一个静默吸收错误的形态）。

第 3 个临时文件的删除复核见实现者上报（它在承载本段之后立即被删除，`Test-Path` → `False`，因此无法把结果写进它自己所承载的正文里）。
