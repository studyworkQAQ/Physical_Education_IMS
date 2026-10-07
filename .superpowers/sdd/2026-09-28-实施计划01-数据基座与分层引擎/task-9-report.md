# Task 9 实现者报告 — 红黄绿分层引擎与黄金用例

**状态：DONE_WITH_CONCERNS**（9 条关切，其中 2 条是控制者文档的照抄源失效、1 条是简报内部自相矛盾）
**commit：`945c8c6`** — `feat: 红黄绿分层引擎与 12 个黄金用例，Z0 数据不足闸门置于决策表首行`
基线 `a1a334c`，分支 `feature/plan-01-data-foundation`，**一个** commit，未 rebase / 未 reset / 未切分支。

---

## 1. 测试数与耗时

| 项 | 值 |
|---|---|
| 基线 | 378 passed |
| 本轮新增 | **18**（`tests/domain/test_stratify.py`，含 `ITEM_DISPLAY_NAMES` 那条） |
| Step 4 时点（Step 5 之前）全量 | **396 passed in 10.69s** |
| `-W error` 全量 | **396 passed in 10.31s**（0 warning，洁净） |
| Step 5 落地后全量 | **396 passed, 1 error in 10.45s**（`--continue-on-collection-errors`）<br>**396 passed, 1 error in 10.46s**（再加 `-W error`）<br>**396 passed in 10.46s**（`--ignore=tests/integration`） |
| AST 架构守卫 | `pytest tests/architecture -q` → **3 passed in 0.03s** |
| `tests/integration` | **1 error**（`ModuleNotFoundError: app.pipeline.run_stratify`，Ruling 5 预期状态，见 §4） |

⚠️ **Step 5 之后不带任何 flag 的 `pytest -q` 会跑 0 条测试**：collection error 会中断整个 session，输出是 `!!!! Interrupted: 1 error during collection !!!! 1 error in 0.63s`。「396 passed」只在加了上面两个 flag 之一时可见 —— 详见**关切 8**。

既有 378 条**一条未改**：`git diff --stat a1a334c..HEAD` 是 `1160 insertions(+)`、**0 deletions**，且改动的既有文件只有 `indicators.py`（19 insertions、0 deletions，纯追加一个常量）。

---

## 2. Step 2 的 RED（原样）

`cd backend; pytest tests/domain/test_stratify.py -v`

```
collecting ... collected 0 items / 1 error
=================================== ERRORS ====================================
_______________ ERROR collecting tests/domain/test_stratify.py ________________
ImportError while importing test module 'C:\...\backend\tests\domain\test_stratify.py'.
Traceback:
C:\Python\Lib\importlib\__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
tests\domain\test_stratify.py:14: in <module>
    from app.domain.stratify import stratify, Layer, RuleId, MIN_VALID_COUNT, explain
E   ModuleNotFoundError: No module named 'app.domain.stratify'
=========================== short test summary info ===========================
ERROR tests/domain/test_stratify.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.17s ===============================
```

与计划 Step 2 的期望逐字一致。

**一处照抄源顺序问题（已自行修正，附证据）**：我最初按 isort 风格把 `app.domain.derive` / `app.domain.indicators` 的 import 排在 `app.domain.stratify` 之前，RED 就变成
`ImportError: cannot import name 'ITEM_DISPLAY_NAMES' from 'app.domain.indicators'`（同样是 RED，但不是计划期望的那一句）。把三行 import 改回计划 Step 1 片段的原始顺序（stratify → derive → indicators）后，得到的就是上面那段 `ModuleNotFoundError: app.domain.stratify`。**结论：计划 Step 1 的 import 顺序是承重的**，照抄时不要重排。

---

## 3. Step 4 的 GREEN（原样）

```
$ pytest tests/domain/test_stratify.py -q
..................                                                       [100%]
18 passed in 0.10s

$ pytest -q
........................................................................ [ 72%]
........................................................................ [ 90%]
....................................                                     [100%]
396 passed in 10.69s

$ pytest -q -W error
396 passed in 10.31s

$ pytest tests/architecture -v
tests/architecture/test_domain_purity.py::test_domain_has_no_forbidden_imports PASSED [ 33%]
tests/architecture/test_domain_purity.py::test_domain_has_no_clock_or_file_access PASSED [ 66%]
tests/architecture/test_domain_purity.py::test_domain_has_no_filesystem_access PASSED [100%]
============================== 3 passed in 0.03s ==============================
```

`test_stratify.py` 的 18 条逐条 PASSED（`-v` 全表已跑，末条为
`test_item_display_names_match_spec_4_2_verbatim PASSED [100%]`）。

---

## 4. Step 7 的 `tests/integration` ERROR（原样，Ruling 5 要求的已知状态）

```
$ pytest tests/integration -v
============================= test session starts =============================
platform win32 -- Python 3.11.1, pytest-9.1.1, pluggy-1.6.0 -- C:\Python\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\whwenhao\Desktop\Physical_Education_ims\backend
configfile: pyproject.toml
plugins: anyio-4.15.1, cov-7.1.0
collecting ... collected 0 items / 1 error

=================================== ERRORS ====================================
___________ ERROR collecting tests/integration/test_golden_cases.py ___________
ImportError while importing test module 'C:\...\backend\tests\integration\test_golden_cases.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Python\Lib\importlib\__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
tests\integration\test_golden_cases.py:4: in <module>
    from app.pipeline.run_stratify import stratify_dataset   # Task 10 提供
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   ModuleNotFoundError: No module named 'app.pipeline.run_stratify'
=========================== short test summary info ===========================
ERROR tests/integration/test_golden_cases.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.55s ===============================
```

**如 Ruling 5 预期**。本轮**没有**实现 `app/pipeline/run_stratify.py`、没有造 `stratify_dataset`（Step 7 明文禁止），`git diff --stat a1a334c..HEAD -- backend/app/pipeline/` 为空可证。

`tests/integration/test_golden_cases.py`（2719 字节）是计划 Step 5 片段的逐字照抄，2 条测试：`test_golden_cases_match_expected_labels` 与 `test_target_layer_distribution_within_tolerance`（含 Ruling 128 的实测数字与 0.4 个百分点余量警告的原样 docstring）。

---

## 5. 八条规则 × 12 个黄金用例命中矩阵

`HIT` = 命中者（`hit_rules[-1]`），`.` = 已评估但未命中（保留在 `hit_rules` 前缀里），`-` = 未评估（命中即停）。
矩阵由生产链路实跑打印（`score_item` → `compute_snapshot` → `national_total` → `derive` → `stratify`），不是手填。

| case | Z0 | R1 | R2 | Y1 | Y2 | Y3 | Y4 | G1 | label | W | C | valid | dominant | trend | `hit_rules` 全文 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GC01 | - | **HIT** | - | - | - | - | - | - | red | 2 | T | 6 | endurance | 稳定 | `["R1"]` |
| GC02 | - | . | **HIT** | - | - | - | - | - | red | 4 | F | 6 | endurance | 稳定 | `["R1","R2"]` |
| GC03 | - | . | . | **HIT** | - | - | - | - | yellow | 1 | F | 6 | strength | 稳定 | `["R1","R2","Y1"]` |
| GC04 | - | . | . | **HIT** | - | - | - | - | yellow | 1 | T | 6 | strength | 稳定 | `["R1","R2","Y1"]` |
| GC05 | - | . | . | . | **HIT** | - | - | - | yellow | 0 | T | 6 | endurance | 稳定 | `["R1","R2","Y1","Y2"]` |
| GC06 | - | . | . | . | . | **HIT** | - | - | yellow | 2 | F | 6 | strength | 稳定 | `["R1","R2","Y1","Y2","Y3"]` |
| GC07 | - | . | . | . | . | **HIT** | - | - | yellow | 3 | F | 6 | endurance | 稳定 | `["R1","R2","Y1","Y2","Y3"]` |
| GC08 | - | . | . | . | . | . | **HIT** | - | yellow | 0 | F | 6 | endurance | 持续下滑 | `["R1","R2","Y1","Y2","Y3","Y4"]` |
| GC09 | - | . | . | . | . | . | . | **HIT** | green | 0 | F | 6 | endurance | 稳定 | `["R1","R2","Y1","Y2","Y3","Y4","G1"]` |
| GC10 | **HIT** | - | - | - | - | - | - | - | insufficient_data | 0 | F | **3** | endurance | insufficient_data | `["Z0"]` |
| GC11 | - | . | . | . | . | . | . | **HIT** | green | 0 | F | 6 | endurance | 稳定 | `["R1","R2","Y1","Y2","Y3","Y4","G1"]` |
| GC12 | - | . | . | . | **HIT** | - | - | - | yellow | 0 | T | 6 | endurance | 稳定 | `["R1","R2","Y1","Y2"]` |

**八行各有命中者**（探针末尾有 `assert all(v >= 1 ...)` 守卫）：
`Z0 1 / R1 1 / R2 1 / Y1 2 / Y2 2 / Y3 2 / Y4 1 / G1 2` = 12。

12 例的构造意图（fixture 里逐条写在 `expected[i].note`）：

| case | 覆盖 | 关键构造 |
|---|---|---|
| GC01 | R1 | 耐力双短板（肺活量 40 分 < P25 50、1000 米跑 20 分 < P25 30）+ 体脂率 22.4% > 男 20% |
| GC02 | R2 | 跨三桶 4 项短板 + 体脂率 15.0% 正常 → R1 不成立、R2 定层；年龄 21 → 年级组「大三、大四」 |
| GC03 | Y1（C=F） | 女生唯一短板 1 分钟仰卧起坐 50 < 女生 P25 60 |
| GC04 | Y1（C=T） | W=1 且 C=True → 证明 R1 要求 W≥2，Y1 在 Y2 之前命中 |
| GC05 | Y2 | W=0 + 体脂率 30.5% > 女 28%；`dominant_bucket` 走 W=0 的「桶内均值最低者」口径（Ruling 100） |
| GC06 | Y3（W=2） | spec §6.1 空洞三的原型：力量双短板 + 体成分正常 |
| GC07 | Y3（W=3） | W=3 仍 < 4 → 钉住 R2 的阈值是 4 不是 3 |
| GC08 | Y4 | 6 项全达标 + 上学年各项高 10 分 → 6 个 delta = −10，总分年均 −8.0 → 持续下滑 → 升黄 |
| GC09 | G1 + **P25 比较符边界** | 6 项得分**恰好等于**各自 P25（50/50/62/50/40/30）→ 严格 `<` 故 W=0；改成 `<=` 则 W=6 → R2 红 |
| GC10 | **Z0** | 3 项缺测 → valid_count=3 < 4；缺测**不当 0 分**（当 0 分则 W=3、valid=6 → Y3 黄，标签就错了） |
| GC11 | **男体脂率 20.0% 边界** | 恰等于阈值 → 严格 `>` 故 C=False → G1 绿；改成 `>=` 则 Y2 黄 |
| GC12 | **女体脂率 28.1% 边界** | 高于阈值 0.1 → C=True → Y2 黄；与 GC11 配对钉住两性别阈值 20 / 28 |

`golden_cases.json`（20657 字节，618 行，LF+CRLF 混合由 `write_text` 在 Windows 上产生，git 会规范化为 LF 入库）结构：
`_meta`（8 个键：purpose / traceability / expected_from / input_schema / bmi / raw_values / percentile_note / muscle_p20_by_group）+ `input`（12）+ `expected`（12）。
**input 只给原始值**：`student_id / sex / age / years / snapshot_muscle_p20 / body_comp{body_fat_pct, muscle_mass_kg, smi} / curr{8 项} / prev{8 项}`，8 项列名与 `RawFitnessRecord` / `FitnessTestResult` 逐字相同（`height_cm, weight_kg, vital_capacity_ml, sprint_50m_s, sit_and_reach_cm, standing_jump_cm, strength_count, distance_run_s`），缺测用 JSON `null`。**没有**任何已算好的 W / C / 得分 / 百分位。6 项原始值由生产 `raw_from_score` 按目标得分反查（「仍拿到该分的最差成绩」，Ruling 22），故 `score_item(反查值) == 目标分` 精确往返，顺带钉住就低取档。

---

## 6. `explain()` 的实际输出全文（生产代码实跑，非手写）

### 四条代表路径

**R1（GC01，体脂超标 + 短板）**
```
红色层 ← 短板 ≥2 项且体成分异常（规则 R1）。依据：你的 肺活量、1000 米跑 在校内同龄男生中低于 P25（6 个有效项里 2 项短板）；体脂率 22.4% 超过男生 20% 阈值；历史趋势「稳定」，国标总分年均变化 +0.0 分。
```
（与 spec §9.2:641 的示例文案同构：「红色层 ← 你的 1000 米跑与引体向上在校内同龄男生中低于 P25，且体脂率 22.4% 超过男生 20% 阈值」）

**Y4（GC08，趋势升级）**
```
黄色层 ← 无短板但趋势持续下滑（趋势只升级、永不降级）（规则 Y4）。依据：6 个有效项均未低于校内同龄男生 P25；体脂率 18% 未超过男生 20% 阈值；历史趋势「持续下滑」，国标总分年均变化 -8.0 分。
```

**G1（GC09，全清）**
```
绿色层 ← 无短板且体成分正常（规则 G1）。依据：6 个有效项均未低于校内同龄男生 P25；体脂率 16.5% 未超过男生 20% 阈值；历史趋势「稳定」，国标总分年均变化 +0.0 分。
```

**Z0（GC10，数据不足）**
```
数据不足 ← 有效项不足 4 项，本日不分层：6 个短板判定项里只有 3 项有效，本日不给出红黄绿标签，已列入异常名单，补测后重算。
```
→ `hit_rules[-1] == RuleId.Z0` 可正常取到，**无 IndexError**（Ruling 125 要的就是这条路径能说话）。

### 其余 8 例（一并贴出，证明 12 例的文案都渲染得出来）

```
[GC02 / red]      红色层 ← 短板 ≥4 项，无条件升红（规则 R2）。依据：你的 肺活量、50 米跑、立定跳远、1000 米跑 在校内同龄男生中低于 P25（6 个有效项里 4 项短板）；体脂率 15% 未超过男生 20% 阈值；历史趋势「稳定」，国标总分年均变化 +0.0 分。
[GC03 / yellow]   黄色层 ← 短板 1 项（规则 Y1）。依据：你的 1 分钟仰卧起坐 在校内同龄女生中低于 P25（6 个有效项里 1 项短板）；体脂率 24% 未超过女生 28% 阈值；历史趋势「稳定」，国标总分年均变化 +0.0 分。
[GC04 / yellow]   黄色层 ← 短板 1 项（规则 Y1）。依据：你的 引体向上 在校内同龄男生中低于 P25（6 个有效项里 1 项短板）；体脂率 26% 超过男生 20% 阈值；历史趋势「稳定」，国标总分年均变化 +0.0 分。
[GC05 / yellow]   黄色层 ← 无短板但体成分异常（规则 Y2）。依据：6 个有效项均未低于校内同龄女生 P25；体脂率 30.5% 超过女生 28% 阈值；历史趋势「稳定」，国标总分年均变化 +0.0 分。
[GC06 / yellow]   黄色层 ← 短板 ≥2 项且体成分正常（规则 Y3）。依据：你的 立定跳远、引体向上 在校内同龄男生中低于 P25（6 个有效项里 2 项短板）；体脂率 17% 未超过男生 20% 阈值；历史趋势「稳定」，国标总分年均变化 +0.0 分。
[GC07 / yellow]   黄色层 ← 短板 ≥2 项且体成分正常（规则 Y3）。依据：你的 肺活量、50 米跑、1000 米跑 在校内同龄男生中低于 P25（6 个有效项里 3 项短板）；体脂率 18.5% 未超过男生 20% 阈值；历史趋势「稳定」，国标总分年均变化 +0.0 分。
[GC11 / green]    绿色层 ← 无短板且体成分正常（规则 G1）。依据：6 个有效项均未低于校内同龄男生 P25；体脂率 20% 未超过男生 20% 阈值；历史趋势「稳定」，国标总分年均变化 +0.0 分。
[GC12 / yellow]   黄色层 ← 无短板但体成分异常（规则 Y2）。依据：6 个有效项均未低于校内同龄女生 P25；体脂率 28.1% 超过女生 28% 阈值；历史趋势「稳定」，国标总分年均变化 +0.0 分。
```

「1000 米跑」「引体向上」（男）与「800 米跑」「1 分钟仰卧起坐」（女）都经 `ITEM_DISPLAY_NAMES` 渲染 —— 没有它这里只能是 `distance_run` / `pull_up_or_sit_up`（Ruling 127）。

### 体成分缺测（`body_fat_pct is None`）不得出现 `None%` 的证据

`BodyCompFlag` 由**生产 `flag_body_comp` 产出**（不是手搓 dataclass），四个变体逐一实跑，每个都断言 `"None" not in text and "nan" not in text.lower()`：

| 变体（生产输入） | 产出的 `BodyCompFlag` | label / hit_rules | `explain()` 全文 |
|---|---|---|---|
| `flag_body_comp(None, None, MALE, 33.20)` | `(abnormal=False, reasons=(), body_fat_pct=None, limit=20.0)` | green / `R1…G1` | 绿色层 ← 无短板且体成分正常（规则 G1）。依据：6 个有效项均未低于校内同龄男生 P25；**体成分数据缺失，本次不参与判定（男生阈值 20%）**；历史趋势「稳定」，国标总分年均变化 +1.0 分。 |
| `flag_body_comp(None, 30.0, MALE, 33.20)` | `(abnormal=True, reasons=('muscle_low',), body_fat_pct=None, limit=20.0)` | yellow / `R1,R2,Y1,Y2` | 黄色层 ← 无短板但体成分异常（规则 Y2）。依据：6 个有效项均未低于校内同龄男生 P25；**肌肉量低于同龄同性别 P20（体脂率缺测，男生阈值 20%）**；历史趋势「稳定」，国标总分年均变化 +1.0 分。 |
| `flag_body_comp(None, 40.0, MALE, 33.20)` + W=2 | `(abnormal=False, reasons=(), body_fat_pct=None, limit=20.0)` | yellow / `R1…Y3` | 黄色层 ← 短板 ≥2 项且体成分正常（规则 Y3）。依据：你的 肺活量、1000 米跑 在校内同龄男生中低于 P25（6 个有效项里 2 项短板）；**体成分数据缺失，本次不参与判定（男生阈值 20%）**；历史趋势「稳定」，国标总分年均变化 +1.0 分。 |
| `flag_body_comp(None, None, FEMALE, 23.70)` | `(abnormal=False, reasons=(), body_fat_pct=None, limit=28.0)` | green / `R1…G1` | 绿色层 ← 无短板且体成分正常（规则 G1）。依据：6 个有效项均未低于校内同龄女生 P25；**体成分数据缺失，本次不参与判定（女生阈值 28%）**；历史趋势「稳定」，国标总分年均变化 +1.0 分。 |

四条全部 ✓ 不含 `None` / `nan`；`limit` 一律非 None（Ruling 97②）正是渲染出「男生阈值 20%」「女生阈值 28%」的前提。
第 2 条同时给出 **`muscle_low` 只能渲染短语、没有数值**的实证（Ruling 126：`BodyCompFlag` 不携带肌肉量读数）。
第 3 条是 Ruling 97③「缺数据导致干预不足」的可视化：W=2 但 C 无从判定 → 落 Y3 黄而不是 R1 红。

### `annual_change == {}` 不得渲染成「各项变化 0 分」的证据

```
输入：annual_change={}, trend=Trend.INSUFFICIENT, national_total=None
输出：绿色层 ← 无短板且体成分正常（规则 G1）。依据：6 个有效项均未低于校内同龄男生 P25；
      体脂率 19% 未超过男生 20% 阈值；历史趋势无可比历史，年均变化无从比较
      （无历史体测，或计分项里有缺测使国标总分不可比）。
```
断言 `"0.0 分" not in text and "+0.0" not in text` 通过（Ruling 99 / Task 8 前向约束 ③）。
GC10 的 fixture 期望里 `trend = "insufficient_data"`、`annual_change` 为 `{}` 也是同一状态的端到端版本。

---

## 7. `reason` 的 8 行映射表全文

生产代码 `app/domain/stratify.py` 的 `_REASON`（私有，实跑打印）：

| RuleId | `reason`（一行规范中文名，**不含任何学生数据**） |
|---|---|
| Z0 | 有效项不足 4 项，本日不分层 |
| R1 | 短板 ≥2 项且体成分异常 |
| R2 | 短板 ≥4 项，无条件升红 |
| Y1 | 短板 1 项 |
| Y2 | 无短板但体成分异常 |
| Y3 | 短板 ≥2 项且体成分正常 |
| Y4 | 无短板但趋势持续下滑（趋势只升级、永不降级） |
| G1 | 无短板且体成分正常 |

Ruling 129 给的示例 `R1 → 「短板 ≥2 项且体成分异常」` 逐字采用。两处阈值数字用 f-string 从 `MIN_VALID_COUNT` / `W_RED_UNCONDITIONAL` 插值，避免出现第二个所有者。

**「只依赖 RuleId」的机械证明**（生产实跑，不是看代码猜）：每条规则各取两个学生数据完全不同的输入，断言 `reason` 相同而 `explain()` 不同：

```
R1: 男(W=2,C=T,bf=22.4,稳定) vs 女(W=5,C=T,bf=33.3,持续下滑) → reason 相同=True ('短板 ≥2 项且体成分异常') label=red/red explain 相同=False
Y3: 男(W=2,C=F,valid=6,稳定) vs 女(W=3,C=F,valid=4,波动大)   → reason 相同=True ('短板 ≥2 项且体成分正常') label=yellow/yellow explain 相同=False
G1: 男(W=0,C=F,valid=6,稳定) vs 女(W=0,C=F,valid=5,稳步提升) → reason 相同=True ('无短板且体成分正常') label=green/green explain 相同=False
Z0: 男(W=0,C=F,valid=3)      vs 女(W=5,C=T,valid=0)          → reason 相同=True ('有效项不足 4 项，本日不分层') label=insufficient_data/insufficient_data explain 相同=False
```

`explain()` 的开头那一句**直接复用 `result.reason`**，故规则名只有 `_REASON` 一个所有者，两者不可能各说一套。

---

## 8. `ITEM_DISPLAY_NAMES` 全文与 spec §4.2 逐行对照

生产代码实跑打印（`app/domain/indicators.py`，本轮**只增**这一个常量，19 insertions / 0 deletions）：

```
bmi                  男=BMI          女=BMI
vital_capacity       男=肺活量        女=肺活量
sprint_50m           男=50 米跑       女=50 米跑
sit_and_reach        男=坐位体前屈     女=坐位体前屈
standing_jump        男=立定跳远      女=立定跳远
pull_up_or_sit_up    男=引体向上      女=1 分钟仰卧起坐
distance_run         男=1000 米跑     女=800 米跑
键集合 == ScoredItem 全集：True；每项都覆盖两个性别：True
随性别变的项：['pull_up_or_sit_up', 'distance_run']
```

与 spec §4.2 计分项表（`:197`–`:205`）逐行对照：

| § | spec §4.2「计分项」列原文 | 单位 | 权重 | `ITEM_DISPLAY_NAMES[男]` | `ITEM_DISPLAY_NAMES[女]` | 一致 |
|---|---|---|---|---|---|---|
| 1 | BMI（身高/体重派生） | kg/m² | 15 | BMI | BMI | ✓（括注是派生说明，不是名称的一部分） |
| 2 | 肺活量 | mL | 15 | 肺活量 | 肺活量 | ✓ |
| 3 | 50 米跑 | s | 20 | 50 米跑 | 50 米跑 | ✓（含全角数字前的半角空格，与 spec 逐字同） |
| 4 | 坐位体前屈 | cm | 10 | 坐位体前屈 | 坐位体前屈 | ✓ |
| 5 | 立定跳远 | cm | 10 | 立定跳远 | 立定跳远 | ✓ |
| 6 | 引体向上（男）/ 1 分钟仰卧起坐（女） | 次 | 10 | 引体向上 | 1 分钟仰卧起坐 | ✓（**随性别变**） |
| 7 | 1000 米跑（男）/ 800 米跑（女） | s | 20 | 1000 米跑 | 800 米跑 | ✓（**随性别变**） |

守卫它的是 `test_stratify.py::test_item_display_names_match_spec_4_2_verbatim`，期望值**字面写在测试里**（`assert ITEM_DISPLAY_NAMES == {…}`，整个 dict 相等 ⇒ 键不多不少、两性别都覆盖），不从被测常量读回。交叉验证：spec §9.2:641 的示例文案用的正是「1000 米跑」与「引体向上」，与男性名逐字相同。

---

## 9. 四次变异验证（全部有测试变红，**无一次空转**）

变异用字节级替换施加/还原（临时脚本 `_tmp_mutate.py`，已删），**全程未用 `git checkout`**，故 sha256 可比。基线（= commit `945c8c6` 的工作树态）：`len=17356`、`sha256=dec84c1779b20671`。

| # | 变异 | 施加后 sha256 / len | 红了哪些（`pytest tests/domain/test_stratify.py -q`） | 失败消息要点 |
|---|---|---|---|---|
| 1 | `RULE_ORDER` 把 `Z0` 移到最后（复现 spec 原错序） | `8f0e1be9725d6f49` / 17356 | **2 failed, 16 passed**：`test_insufficient_data_when_valid_count_below_4`、`test_insufficient_data_beats_all_rules` | 前者 `assert <Layer.GREEN:'green'> == <Layer.INSUFFICIENT:'insufficient_data'>`（**正是 spec 原缺陷的形态：W=0∧¬C 的缺测学生被 G1 提前吃掉变绿**）；后者 `assert <Layer.RED:'red'> == <Layer.INSUFFICIENT>`（W=5∧C 先命中 R1） |
| 2 | `RULE_ORDER` 里 `R1`/`R2` 互换 | `91cfe8fc256df1a1` / 17356 | **1 failed, 17 passed**：`test_R1_takes_priority_over_R2` | `assert <RuleId.R2:'R2'> == <RuleId.R1:'R1'>`（`hit_rules[0]` 变成 R2） |
| 3 | `Y4` 判据 `is Trend.DECLINING` → `is not Trend.IMPROVING` | `0a15123f33d0b5e3` / 17360 | **3 failed, 15 passed**：`test_Y4_does_not_fire_for_volatile_or_improving`、`test_G1_all_clear_is_green`、`test_valid_count_exactly_4_is_stratified` | 三条都是 `assert <Layer.YELLOW:'yellow'> == <Layer.GREEN:'green'>`（`稳定` 与 `波动大` 被误升黄；后两条的 `mk()` 默认 trend=STABLE，故一并暴露） |
| 4 | `Z0` 命中时 `hit_rules` 返回空元组（复现计划原文的错） | `fb4e43e19a9ad6f4` / 17385 | **1 failed, 17 passed**：`test_insufficient_data_when_valid_count_below_4` | `assert () == (<RuleId.Z0:'Z0'>,)`，`Right contains one more item` |

**变异 4 的第二半（「原文那个错真的会崩」）单独取证**：该测试的**第一条**断言（`hit_rules == (Z0,)`）先失败，故 `explain()` 那行在测试里根本走不到。为证明崩溃真实存在，在变异 4 施加状态下直接调生产函数：

```
$ python -c "... d=DerivedResult(..., valid_count=3, ...); r=stratify(d); print(r.label.value, r.hit_rules); print(explain(r,d))"
label= insufficient_data hit_rules= ()
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "...\backend\app\domain\stratify.py", line 339, in explain
    rule = result.hit_rules[-1]
IndexError: tuple index out of range
```
→ Ruling 125 的论断成立：计划 Step 3 原文那句「`hit_rules` 为空元组」会让 Z0 路径上的 `explain()` **当场 IndexError**，而 Z0 恰恰是最需要向学生解释的一条。

### 三重还原证据（每次变异后都做了，四次全过）

| # | ① `git diff --stat` 空 | ② 变异标记双路 0 命中 | ③ 还原后重跑 |
|---|---|---|---|
| 1 | `git-diff-stat-empty=True` | python 读字节 `hits=0`；ASCII `Select-String -Pattern "^    RuleId\.Z0,$"` → 命中 1 行且**行号 69**（= `RULE_ORDER` 的第一项，Z0 已回到首位） | `396 passed in 10.69s` |
| 2 | `git-diff-stat-empty=True` | python `hits=0`；`Select-String "RuleId\.R2,"` → 行号 **71**（在 R1 的行 70 之后，顺序已复原） | `396 passed in 10.87s` |
| 3 | `git-diff-stat-empty=True` | python `hits=0` **且** `Select-String "is not Trend.IMPROVING"` → **0**、`Select-String "and derived.trend is Trend.DECLINING"` → **1**（双路） | `396 passed in 10.57s` |
| 4 | `git-diff-stat-empty=True`（且 `git status --short` 只剩临时探针） | python `hits=0` **且** `Select-String "hit_rules=\(\) if rule"` → **0**、`Select-String "hit_rules=\(\*evaluated, rule\)"` → **1**（双路） | `396 passed in 10.59s`，`-W error` 亦 `396 passed in 10.52s` |

四次还原后 sha256 都回到 **`dec84c1779b20671`**、len 都回到 **17356**（与 commit 态逐字节相同）。

---

## 10. `git diff` 与禁区证明

```
$ git diff --stat a1a334c..HEAD
 backend/app/domain/indicators.py               |  19 +
 backend/app/domain/stratify.py                 | 352 ++++++++++++++
 backend/tests/domain/test_stratify.py          | 128 +++++
 backend/tests/fixtures/golden_cases.json       | 618 +++++++++++++++++++++++++
 backend/tests/integration/test_golden_cases.py |  43 ++
 5 files changed, 1160 insertions(+)
```
**0 deletions** ⇒ 既有 378 条测试的断言一行未改、既有生产代码一行未删；`indicators.py` 是纯追加。

```
$ git diff --stat a1a334c..HEAD -- backend/app/seed/ backend/data/
（无输出）  empty=True
$ git diff --stat a1a334c..HEAD -- backend/app/domain/derive.py backend/app/domain/percentile.py backend/app/db/ backend/app/pipeline/ backend/app/adapters/
（无输出）  empty=True
$ Test-Path backend/pe.db            → False        （Ruling 68）
$ (Get-ChildItem backend/data/seed -Force).Count → 0 （保持空）
```
`backend/app/seed/` 三个 CSV 的哈希 `498AA3256678B01A` / `1234025C05843B27` / `835A98FCC0779B51` 因此不可能受影响（该目录零改动）。

**⚠️ 与简报 §5 第 1 条的差异：commit 是 5 个文件，不是 6 个 —— `backend/tests/domain/test_indicators.py` 本轮未改动。** 理由与取舍见**关切 1**。

---

## 11. 关切（每条附可复现方法；标注读的是生产状态还是重新推导）

### 关切 1（简报自相矛盾，需裁定）— 「六个文件」与「`test_stratify.py` 18 passed / 全量 396」不能同时成立；我选了后者，故 commit 只有 5 个文件

- 简报 §3 Step 1：「把计划里那 **17 条** `test_stratify.py` 测试原样落地，再加 **1 条** `ITEM_DISPLAY_NAMES` … → **18 条**」；§3 Step 4 与 §5 第 2 条：`pytest tests/domain/test_stratify.py -v` → **18 passed**、全量 **378 → 396**；计划 `:1780` 同口径（「原 17 条 + `ITEM_DISPLAY_NAMES` … 的 1 条」）。
- 但简报 §5 第 1 条要求 `git add` 含 **`test_indicators.py`**（六个文件）。若那条测试放进 `test_indicators.py`，`test_stratify.py` 就只有 **17** 条，Step 4 / Step 7 的期望数当场失效（总数仍是 396）。
- **我的处置**：按出现三次的数字口径（Step 1 / Step 4 / §5 第 2 条）把第 18 条放进 `test_stratify.py`，不动 `test_indicators.py`。
- **可复现**（生产状态）：`cd backend; pytest tests/domain/test_stratify.py -q` → `18 passed`；`git diff --stat a1a334c..HEAD` → 5 files；`Select-String -Path backend/tests/domain/test_indicators.py -Pattern "DISPLAY"` → **0 命中**（交叉验证：`python -c "print(open('backend/tests/domain/test_indicators.py','rb').read().count(b'DISPLAY'))"` → 0）。
- **附带（硬规矩 #11 第六次落空的同形态）**：计划 **Step 7**（`:1838`）仍写 `Expected: PASS，17 passed`，而同一份计划 Step 4（`:1780`）写 18 passed。简报 §3 Step 7 已改成 18，但**计划正文没改**——Ruling 125 那轮改了 Interfaces / Step 3 / Step 1，漏了 Step 7 的期望数。
- **需裁定**：是否要**另**在 `test_indicators.py` 里加一条同口径测试（则总数变 397、Step 4 数字要改），还是维持现状（我倾向维持：`ITEM_DISPLAY_NAMES` 的消费者是 `explain()`，测试与消费者同住一处，且避免同一个期望值有两个所有者）。

### 关切 2（承重，计划内部不相容，已按测试实现）— 「`hit_rules` = 本次求值评估过的规则序列」与「`Z0` 在 `RULE_ORDER` 第一位」与计划 Step 1 的 `hit_rules[0] == RuleId.R1` 三者不相容

- 我先按「凡评估过就进序列」实现（Z0 对每个学生都求值 ⇒ 每个学生的 `hit_rules` 都以 `Z0` 开头），**实跑红了**：
  `pytest tests/domain/test_stratify.py -q` → `1 failed, 17 passed`，`test_R1_takes_priority_over_R2: assert <RuleId.Z0:'Z0'> == <RuleId.R1:'R1'>`（生产状态证据，改前实跑）。
- **裁定依据**：计划 Step 1 的那 17 条是「逐字照抄」的照抄源、且 Step 4 要求 18 passed，故测试优先。实现改为：**Z0 未触发时不进前缀**（它是闸门，不是分层规则 —— Ruling 125 自己写的「不占用 R/Y/G 的编号空间」正好是这个意思）；Z0 命中时 `hit_rules == (RuleId.Z0,)`。求值**顺序**仍完全由 `RULE_ORDER` 驱动，所以变异 1 依然能红 2 条（见 §9），守卫没有空转。
- **后果（Task 10 要知道）**：非 Z0 学生的 `hit_rules` 最长是 `"R1,R2,Y1,Y2,Y3,Y4,G1"` = 23 字符，`String(128)` 绰绰有余；`"Z0"` 只单独出现。
- **需裁定**：`models.py:423` 的注释「它是**本次求值评估过的规则 ID 序列**」现在需要一句限定（「Z0 闸门未触发时不入序列」）。我不能碰 `app/db/`（简报 §4），故留给你。

### 关切 3（**控制者的照抄源失效，会让 Task 10 写错库**）— `models.py:427` 仍写「`insufficient_data` 时为空串」，与 Ruling 125 / spec §6.2 勘误直接矛盾

- **可复现**（生产状态）：`Select-String -Path backend/app/db/models.py -Pattern "insufficient_data"` → 命中 3 行，其中 **`:427`** 全文是「的依据。``insufficient_data`` 时为空串。」；对照 spec `:348`「Z0 命中时 `hit_rules` 就是 `["Z0"]`，**不是空串**」与计划 `:1764`「`hit_rules` 在 Z0 命中时是 `(RuleId.Z0,)`，不是空元组」。交叉验证（中文，双路）：`python -c "d=open('backend/app/db/models.py','rb').read(); print(d.count('时为空串'.encode('utf-8')))"` → **1**。
- **后果**：Task 10 落库时若照 `models.py` 的注释写 `""`，则 ① `golden_cases.json` 的 GC10 期望 `["Z0"]` 会红（好事，能抓到）；② 但计划 `:1952` 的 `test_hit_rules_are_persisted` 写的是 `assert all(r.hit_rules for r in rows if r.label != "insufficient_data")` —— **它把 insufficient_data 行排除在外**，所以「Z0 行写了空串」这件事在 Task 10 的测试网里**没有别的守卫**。
- 这是硬规矩 #11「改一处规格必须 grep 全部照抄源」的**第六次**落空，形态与前五次略有不同：Ruling 125 grep 的是**计划全文**，而这一处照抄源在**生产代码的 docstring** 里（`app/db/models.py`）。建议把规矩 #11 的搜索范围明确扩到「仓内所有 docstring/注释」，而不只是计划与 spec。
- **需裁定**：由你（或 Task 10 派单）改 `models.py:423-427` 的注释；顺带核对 `:424`「7 条规则命中即停」（Z0 是闸门，故「7 条分层规则」仍准确，但若改成「8 行」会与本报告的口径冲突，建议写成「7 条分层规则 + Z0 闸门」）。

### 关切 4（**黄金用例的覆盖面比计划设想的小**）— 12 人 < `MIN_SAMPLE = 30`，故 `compute_snapshot` 对全部 28 个组都降级为国标常模；这 12 例守卫的是 `source="national"` 那一路，校内百分位那一路在黄金用例里**零覆盖**

- **可复现**（生产状态）：探针用 12 人的 curr 得分调生产 `compute_snapshot`，打印 `81 行得分 → 28 组快照`，每组 `src=national`、`n ∈ {1,3,7}`（如 `bmi/male/大一、大二 n=7`、`distance_run/female/大三、大四 n=1`），并 `assert all(r.source == "national")` 通过。重跑方法：读 `golden_cases.json` 的 `input`，按 `_meta.expected_from` 的链路调 `score_item` + `compute_snapshot(rows, standard())`，看每行的 `source` / `sample_size`。
- **两个后果**：① Task 10 的 `stratify_dataset(list)` 给这 12 人填的 `percentile_source` 必然是 `"national"`，别写死 `"school"`、也别为了「好看」去放宽 `MIN_SAMPLE`；② 这 12 例的 P25 判定线是 `national_norm` 推导值（男 大一、大二 = `50/50/62/50/40/30`，女 = `64/50/62/50/60/40`），**与 12 人自己的成绩分布无关** —— 简报 §3 Step 6 说的「P25 用生产 `compute_snapshot` 在这 12 人自己的数据上算」我照做了，但在 n<30 时它的产物就是常模兜底行，这是生产行为、不是我抄了个数。
- 已写进 fixture 的 `_meta.percentile_note`，Task 10 读 fixture 时就能看到。
- **需裁定**：是否要在 Task 10/11 补一组「≥30 人 → `source="school"`」的黄金用例（本轮 12 例的清单是计划钉死的，我没有自行加人）。

### 关切 5（**计划 Step 6 的输入清单少两项，照字面做会让 Y4 那例永不可能命中**）— 「6 个短板判定项的原始值 + 体成分 + 上学年成绩」喂不进生产链路

- `derive` 要求 `curr_scores` / `prev_scores` **含全部 7 个计分项的键（含 bmi）**（Ruling 101），而 BMI 由身高体重合成 ⇒ 只给 6 项就缺 `bmi` 键；即便补了键而值为 `None`，`national_total` 也返回 `None` ⇒ `classify_trend` 归 `INSUFFICIENT` ⇒ **趋势永远不是「持续下滑」，Y4 那一例（计划 Step 6 明列）永不可能命中**。
- **可复现**（生产状态，四段实跑）：
  - `national_total({6 项})` → `None`（不是 0）；
  - `derive(curr_scores={6 项}, …)` → `KeyError: "curr_scores 必须含全部 7 个计分项的键（含 bmi），实际缺少 ['bmi']…"`；
  - 七键齐但 `bmi=None`：`national_total` → `None`，`classify_trend(prev, curr, None, None, 1.0)` → `insufficient_data`（**即使 6 项 delta 全为 0**）；
  - 七项齐全（身高体重 → BMI）：`national_total` → `71`，`classify_trend(curr 全 70, prev 全 80, 71→80, years=1.0)` → `持续下滑`。
- **我的处置**：fixture 的 `curr` / `prev` 各给**8 项原始测量**（列名与 `RawFitnessRecord` / `FitnessTestResult` 逐字相同），BMI 由 `_meta.bmi` 写明的口径合成：`bmi = round(weight_kg / (height_cm/100)**2, 1)`（与生成器 `app/seed/fitness.py:1076` 逐字一致），再走 `score_item` 正查（BMI 非单调，**不能**走反查）。
- **需裁定**：把计划 Step 6 的「6 个短板判定项的原始值」改成「8 项原始测量值」，否则 Task 10 的实现者可能照计划字面只解析 6 项。

### 关切 6（覆盖面，我刻意选的稳健侧）— 12 例里 `muscle_low` 那一支**零覆盖**：`snapshot_muscle_p20` 给了但不承重

- 简报 §4 禁止碰 Ruling 102/120/121（肌肉量 P20 无生产者），§3 Step 6 又说「若需要肌肉量 P20，在 fixture 里手工给定并在 note 里写明」。我的取舍：**每条 input 都带 `snapshot_muscle_p20`**（数值取 Ruling 128 的实测：male `33.20`/`33.56`、female `23.70`/`23.60`，按 (性别 × 年级组) 逐人给，`_meta.muscle_p20_by_group` 有汇总），但**12 人的肌肉量全部高于本组 P20**，故没有任何一例的 `C` 依赖它。
- 理由：若让某例的 `C` 只由 `muscle_low` 触发，则 Task 10 一旦没接线（传 `None`）该例就会红 —— 那是**契约未定**而不是算法错，会污染 Task 10 的信号；反之现在 Task 10 传值或传 `None`，12 例的期望都成立。
- **可复现**（生产状态）：探针逐例打印 `reasons`，C=True 的 4 例全是 `('body_fat_high',)`、C=False 的 8 例全是 `()`，无一例出现 `'muscle_low'`。
- **需裁定**：Ruling 102/121 落地后（Task 10 预检），是否把 GC04 或另加一例的肌肉量压到 P20 以下，让 `muscle_low` 进入黄金用例网。

### 关切 7（文案口径，我没擅自改）— `reason` 里 Y3 / G1 的「体成分正常」在**体成分缺测**时是过度断言

- `C = False` 有两种成因：真正常，或**两项都缺测/无判定线**（Ruling 97③）。`reason` 按 Ruling 129 只能由 `RuleId` 单射得出，故它无法区分，只能说「体成分正常」。
- **可复现**（生产状态）：`flag_body_comp(None, 40.0, Sex.MALE, 33.20)` + `W=2` → `label=yellow`、`reason='短板 ≥2 项且体成分正常'`，而同一条的 `explain()` 正确地说「**体成分数据缺失，本次不参与判定（男生阈值 20%）**」（§6 表格第 3 行）。即：长文案不撒谎，**一行短文案（日志/API/大屏列表用的那个）撒谎**。
- 我**没有**擅自改词，因为「体成分正常」是 spec §6.1 空洞三表格与 §6.2 第 6 行自己的用词（`W ≥ 2 AND NOT C`）。
- **需裁定**：(a) 维持（spec 用词，且 `explain()` 已如实披露）；(b) 把 Y3/G1 的 `reason` 改成「体成分未判为异常」——这仍是 `RuleId` 的单射，不违反 Ruling 129，但要同步改 spec §6.1/§6.2 的措辞，否则又造出一处「一个口径两个所有者」。

### 关切 8（会影响 Task 10 的验收命令）— Step 5 之后**不带 flag 的全量 `pytest -q` 跑 0 条测试**

- collection error 会中断整个 session：`pytest -q` → `ERROR tests/integration/test_golden_cases.py` + `!!!! Interrupted: 1 error during collection !!!!` + **`1 error in 0.63s`**（passed 数为 0，不是 396）。
- **可复现**（生产状态，三条命令对照）：
  - `pytest -q` → `1 error in 0.63s`
  - `pytest -q --continue-on-collection-errors` → `396 passed, 1 error in 10.45s`
  - `pytest -q --ignore=tests/integration` → `396 passed in 10.46s`
- **需裁定 / 传给 Task 10**：① 简报 §5 要求的「测试数 378 → 396」只有在后两条命令下可见，报告里我三种都贴了；② Task 10 Step 6 的期望数应是 **398 passed**（396 + 那 2 条集成测试转绿）且**不再有 error**；③ 在 Task 10 落地之前，任何人（包括评审）跑全量都必须带 flag，否则会误判成「测试全没了」。

### 关切 9（脆性预警，非缺陷）— GC09 把 6 项得分**恰好**放在国标常模 P25 上，故它对 `national_norm` 的假设敏感

- GC09 是为了钉住 spec §14 #21 的**严格小于**（`score < p25`）而刻意构造的：6 项得分 = `50/50/62/50/40/30`，正是生产 `national_norm` 给 male/大一、大二 的 P25。改成 `<=` 则 W 从 0 跳到 6 → 标签从 green 跳到 red（R2），当场暴露 —— 这是想要的敏感性。
- 但 spec §14 #24 明写这个常模是**占位**（「均匀分布于量程」的假设，换真实常模只需替换 `national_norm` 一个函数）。**换掉它 GC09 就会红**，而且红得「看起来像算法回归」。
- **可复现**（生产状态）：探针打印 male/大一、大二 六项 `p25 = 50.00/50.00/62.00/50.00/40.00/30.00`，与 GC09 的目标得分逐项相同；`raw_from_score` 反查出的原始值见 fixture `input[8].curr`。
- **需裁定 / 传给后续任务**：日后替换 `national_norm` 时，正确处置是**重算 fixture**（跑一遍本报告 §5 的链路，更新 `expected`），**不是**放宽 #21 的比较符、也不是把 GC09 删掉。已写进 `_meta.percentile_note`。

### 附：一次工具/磁盘分歧的观察（第 13 次，方向是「工具回显多了内容」）

变异 4 还原后，我用 `SearchReplace` 改临时探针，工具回显里把 `app/domain/stratify.py` 的第 24–26 行显示成「`from dataclasses import dataclass` + **一个多出来的空行** + `from enum import Enum`」。shell 三路复核证明磁盘上没有那个空行：`len=17356`、`sha256=dec84c1779b20671`（与 commit 态逐字相同）、`git diff --stat` 空。第二次 `SearchReplace` 也如实回了「no changes」。**结论：纪律照旧 —— 回显不是证据，只有 shell 是。**（本轮 0 次写盘事故：4 次新建/编辑全部正确落盘。）

---

## 12. 前向约束（Task 10 / Task 11 派单必须带上）

### Task 10 消费 `stratify` / `StratResult` 的注意事项

1. **`hit_rules` 是「已评估序列」而不是「命中集合」**：最后一项才是命中者（命中即停 ⇒ 最多一条命中）。非 Z0 学生的序列从 `R1` 起、**不含 `Z0`**（Z0 是闸门，未触发就不入序列，见关切 2）；Z0 命中时序列就是 `("Z0",)`。落库时逗号连接即可，最长 23 字符（`String(128)` 够）。
2. **`Z0` 命中时必须写 `"Z0"`，不是空串**：`models.py:427` 的注释是错的（关切 3），以 spec §6.2 勘误 / Ruling 125 / `golden_cases.json` 的 GC10 期望为准。空串会让 `explain()` 的 `hit_rules[-1]` 抛 `IndexError`（变异 4 已实证：`stratify.py:339`）。
3. **`reason` 不含学生数据 ⇒ 可直接入库、进日志、上大屏列表**，不要另造第二份规则名映射（Ruling 129）。要含数值的文案一律调 `explain(result, derived)`，它的开头那一句就是 `result.reason`。
4. **`percentile_source` 该怎么填**：Ruling 120 裁定 `valid_count = 0` 时填 `"none"`，并需**扩 ORM 的 CHECK 取值域** —— `StratificationResult.PERCENTILE_SOURCES` 当前是 `{"school", "national"}`（`models.py:436`），约束名 `ck_stratification_result_percentile_source`（`:456-460`）；列宽 `String(8)`，`"none"` 4 字符放得下，但**集合与 CHECK 必须同步扩**，否则插行时 IntegrityError。**两个待裁定点**：① Ruling 120 只说了 `valid_count = 0`，而 Z0 的触发条件是 `valid_count < 4` —— `valid_count ∈ {1,2,3}` 时判定线是存在的（GC10 就是 3），该填实际来源还是也填 `"none"`？② 同一学生的 6 项可能**混用** school 与 national（某组降级、某组没降），此时填哪一个？建议「任一项用了兜底就填 `national`」，但这是新口径，须先裁定。
   **另附实测**：黄金用例那 12 人因 n < 30 全部降级，`percentile_source` 必为 `"national"`（关切 4），别写死 `"school"`。
5. **`stratify_dataset(cases["input"])` 必须走的链路**（fixture 的期望值就是按它算出来的，见 `_meta.expected_from`）：
   8 项原始值 → `bmi = round(weight_kg/(height_cm/100)**2, 1)` → `score_item` × 7（**表由 `app.refdata.standard()` 注入**）→ `compute_snapshot(rows, table)`（`rows` 只含 `score` 非 `None` 的行，每行 `{"sex","age_group","item","score"}`）→ `national_total` 算**两侧**总分 → `derive`（11 参数：`age_group=age_group_of(record["age"])`、`years=record["years"]`、`snapshot_muscle_p20=record["snapshot_muscle_p20"]`、整张快照直接传、**不预筛**）→ `stratify` → `explain`。
   上学年原始值同样要过 `score_item`；两学年都用 `age_group_of(age)` 还是 `age_group_of(age-1)` 都安全 —— 12 例的年龄是 19 与 21，`age` 与 `age-1` 落在**同一个**年级组（19→18 都是「大一、大二」，21→20 都是「大三、大四」），故 `prev == curr` 的 10 例 delta 恒为 0、趋势恒为「稳定」，不受这个选择影响。
6. **`results` 的顺序必须与 `input` 一致**（测试用 `zip(cases["expected"], report.results)` 逐位对比），`distribution` 的键必须含 `insufficient_data`（= `Layer.INSUFFICIENT.value`），12 例里有 1 例是它。
7. **GC10 的 `trend = "insufficient_data"` 与 `annual_change = {}` 是合法状态**，不要当异常抛（Ruling 99 / Task 8 前向约束 ⑤）；它的 `national_total` 是 `None`（七项里有缺测），同层内排序要能容忍 `None`。
8. **`--continue-on-collection-errors`**：`run_stratify.py` 落地前，全量 pytest 会被 collection error 中断（关切 8）。Task 10 Step 6 的期望数是 **398 passed、0 error**。
9. **Y4 的触发面偏向**（Task 8 前向约束 ⑥ 沿用）：整数口径的 `Delta` 系统性比连续口径更负 `0.10…0.30` 分，故更容易判 `DECLINING`、Y4 更容易触发。Ruling 128 的实测分布（有线 yellow 47.6%、green 30.4%）已含这个偏向，**不要放宽容差**，green 只剩 0.4 个百分点。
10. **不要为了让集成测试变绿而改 `golden_cases.json` 的期望值**。若 `national_norm`（关切 9）或 P25 比较符（spec §14 #21）变更，正确处置是按 §5 的链路**重算** fixture 并在报告里写明，不是改断言、更不是删用例。

### Task 11（前端 / API）

1. **`ITEM_DISPLAY_NAMES` 是中文项目名的唯一所有者**（`app/domain/indicators.py`），前端与 API 一律 import 它，不得在 TS/模板里重抄一份「1000 米跑 / 800 米跑」——名称随性别变，抄一份就会有第二份口径（Ruling 127 的归属理由）。
2. 学生端「分层可解释性展开」（spec §9.2）直接用 `explain()` 的返回值，它已是完整中文句子；`reason` 用于列表/日志。素质桶**没有**中文名口径（`ITEM_BUCKET` 的值是 `endurance` 这类英文 token），故 `explain()` 刻意不渲染 `dominant_bucket` —— 前端若要显示桶名，须先在 spec 里定中文口径，不要自行翻译。
3. `Layer` / `RuleId` 都是 `str` 枚举，`Layer.RED == "red"`、`RuleId.Z0 == "Z0"` 直接成立，序列化不必再翻译。

---

## 13. 交付物清单与收尾

**新增/改动（5 个文件，1160 insertions / 0 deletions）**
- `backend/app/domain/stratify.py`（352 行，17356 字节，LF）— 导出面**恰好**是简报允许的 8 个符号：`Layer` / `RuleId` / `RULE_ORDER` / `MIN_VALID_COUNT` / `W_RED_UNCONDITIONAL` / `StratResult` / `stratify` / `explain`；其余（`_HOLDS` / `_LAYER_OF` / `_REASON` / `_SEX_WORD` / `_LAYER_WORD` / `_W_AT_LEAST_TWO` / `_holds_*` / `_weakness_text` / `_body_comp_text` / `_trend_text`）一律下划线私有。实跑 `dir()` 复核：公开名里除上述 8 个外只有 import 进来的名字（`Callable` / `DerivedResult` / `Enum` / `ITEM_DISPLAY_NAMES` / `Sex` / `Trend` / `WEAKNESS_ITEMS` / `dataclass`），**没有新增计划未列的导出符号**。
  无 I/O、不 import `app.refdata`、不碰时钟（3 个 AST 守卫全绿，§3）。
- `backend/app/domain/indicators.py`（+19 行，纯追加 `ITEM_DISPLAY_NAMES`；既有函数与常量一行未改）
- `backend/tests/domain/test_stratify.py`（128 行，18 条）
- `backend/tests/integration/test_golden_cases.py`（43 行，2 条，**预期 ImportError**）
- `backend/tests/fixtures/golden_cases.json`（618 行 / 20657 字节，`_meta` + 12 input + 12 expected）

**禁区复核**：`backend/pe.db` 不存在；`backend/data/seed/` 0 个条目；`backend/app/seed/`、`backend/app/db/`、`backend/app/pipeline/`、`backend/app/adapters/`、`derive.py`、`percentile.py` 零改动（§10）。

**临时探针（全部已删，逐个 `Test-Path` 复核 False，见下方 shell 输出）**：
`_tmp_probe_lines.py`、`_tmp_probe_golden.py`、`_tmp_probe_missing.py`、`_tmp_probe_api.py`、`_tmp_probe_seven.py`、`_tmp_mutate.py`、`_tmp_golden_out.txt`、`_tmp_missing_out.txt`、`_tmp_api_out.txt`、`_tmp_seven_out.txt`、`_tmp_step7.txt`、`_tmp_commitmsg.txt`（commit message 用的无 BOM UTF-8 临时文件，`git commit -F` 后立即删）。

### shell 双路复核（报告文件本身 + 收尾证据，原样贴出）

```
$ Get-Item task-9-report.md | Select-Object Name,Length      # 见下方“报告文件复核”
$ python -c "d=open(...,'rb').read(); print(len(d), d.count('关切'.encode('utf-8')))"

$ cd backend; foreach ($f in 11 个临时探针) { Test-Path $f }
_tmp_probe_lines.py -> False
_tmp_probe_golden.py -> False
_tmp_probe_missing.py -> False
_tmp_probe_api.py -> False
_tmp_probe_seven.py -> False
_tmp_mutate.py -> False
_tmp_golden_out.txt -> False
_tmp_missing_out.txt -> False
_tmp_api_out.txt -> False
_tmp_seven_out.txt -> False
_tmp_step7.txt -> False
--- leftovers matching _tmp* ---
0
--- pe.db / data/seed ---
False
0
--- final full run ---
ERROR tests/integration/test_golden_cases.py
396 passed, 1 error in 10.49s

$ git log --oneline -1
945c8c6 feat: 红黄绿分层引擎与 12 个黄金用例，Z0 数据不足闸门置于决策表首行

$ git status --short
（无输出 —— 工作树干净；`.superpowers/` 在 .gitignore:20 内，故本报告不入库）
[end]
```

**报告文件复核**（写完后的双路取证，见下节由 shell 打印）：`Get-Item.Length` 与 python 读字节数一致、
中文字符串计数非 0（`关切` 应 ≥ 10 次、`黄金用例` 应 ≥ 5 次）、`\r\n` 计数（python 写入为 LF）。
