# Task 7 + Task 8 合并复审

评审对象：`c72b53f..edf718a -- backend/`（4 文件 +1463），HEAD = `edf718a`，评审开始时工作树干净。
评审方式：只读 + 实跑探针 + 6 次变异（全部完全还原）。**未修改任何受版本控制的文件**（末尾附 `git status --short`）。
临时探针写在 `%TEMP%`，共 15 个（`rv_probe1..15.py`），评审结束已逐个删除并 `Test-Path` 复核为 False。

---

## 结论

| 对象 | 结论 |
|---|---|
| **Task 7（`percentile.py`）** | **PASS_WITH_CONCERNS** — 生产行为我逐值独立复算过，**没有发现一处行为缺陷**；但有 1 条 Major 守卫缺口（`age_group` 不校验）、1 条 Critical 级测试空转（分组键的 `item` 维度零覆盖）、以及 4 处写进 spec/docstring/账本的**数字不成立** |
| **Task 8（`derive.py`）** | **PASS_WITH_CONCERNS** — `classify_trend` 与 spec §6.3 **等价**（第三次独立 500 人对账 500/500），`national_total` 口径正确；但有 2 条 Critical 级测试空转（`body_comp` 整字段零断言、`test_bmi_never_counted_as_weakness` 空转）、3 条 Major 守卫缺口（total 值不校验、`years` 不校验、加权求和仍有第二个所有者） |
| **合并结论** | **PASS_WITH_CONCERNS** — 两个任务的**生产代码可以进 Task 9**；但**测试网有三个洞**（变异 D/E/F 各让全量 369 条测试保持全绿），且**计划 :1668-1671 的 Task 9 照抄源已失效**（实测 `TypeError`）。这三条 Critical + 一条 M6 建议在派 Task 9 之前处理，否则 Task 9 会以「全绿」的姿态建立在一层没有守卫的地基上 |

**Critical 3 条 / Major 6 条 / Minor 7 条。**

---

## Task 7 独立结论（`percentile.py` 逐行阅读的结果）

我按简报要求对 `percentile.py` 做了独立逐行阅读，并**不看实现、自己从 Ruling 84 的假设重写了一遍推导**去对拍：

**行为层面：没有发现缺陷。** 逐条核对结果：

| 检查项 | 结论 | 证据 |
|---|---|---|
| 分组键 `(sex, age_group, item)` | 正确，`Sex(...)` / `ScoredItem(...)` 对非法值响亮失败 | `percentile.py:203`；实测 `item='muscle_mass_kg'` → `ValueError: 'muscle_mass_kg' is not a valid ScoredItem` |
| `np.percentile(..., method="linear")` 用法 | 正确，档位一律取自 `PERCENTILES`，无第二份手抄 | `percentile.py:216-218`、`:32-34`、`:69-75` |
| `MIN_SAMPLE` 边界 | `< 30` 降级、`= 30` 用本校，双向钉住 | 实测 n=1/28/29 → `source=national` 且 `sample_size` = 真实值；n=30/31 → `source=school` |
| 降级行 `sample_size` 写真实值、常模行自己写 0 | 正确，且用 `dataclasses.replace` 机械保证「除 sample_size 外逐字段等于 national_norm」 | `percentile.py:209-214`；实测 `replace(fb, sample_size=0) == national_norm(...)` → `True` |
| `national_norm` 的推导 | **我用独立实现算的 24 组 × 5 档 = 120 个值与生产逐值全等，0 处差异**；逆序 **0** 组 | 探针 rv_probe2 |
| 方向感知 | 从表推断（比较 `score_item(lo)` 与 `score_item(hi)`），未 import 私有名 `_lower_is_better` | `percentile.py:124-126`；实测 `lower_is_better` 只对 `sprint_50m` / `distance_run` 为 True |
| 不 import `app.refdata`（Ruling 87） | **成立**：`refdata` 只出现在 `:8-10` 的 docstring；import 只有 `dataclasses` / `numpy` / `indicators` / `tables` | Grep `refdata\|import ` 于 `percentile.py` |
| 契约里没有 `student_id`（Ruling 88） | **成立**：只出现在 `:175-176` 的「声明它不在契约里」那段；多余键实测不被拒绝（测试助手 `rows()` 仍带它，5 条 `compute_snapshot` 测试全绿） | Grep + 实跑 |
| `PercentileRow` ↔ ORM `PercentileSnapshot` | **一一对应**：dataclass 10 个字段全部是 ORM 列；ORM 多出的恰是 `{id, semester_id, computed_on, batch_id}`（Ruling 86 说明的归属） | 探针 rv_probe3 §D |
| `source` 取值域 | `{"school","national"}` 与 `PercentileSnapshot.SOURCES` 及 `StratificationResult.PERCENTILE_SOURCES` 三者同域；`sex` 与 `Student.SEXES = {"male","female"}` 同域 | `models.py:360/380-381/436` |
| 返回顺序规范序 | 实测 `snap == sorted(snap, key=(item.value, sex.value, age_group))` → True | 探针 rv_probe2 |
| `lookup_p25` 返回 `None` 的语义 | 被 `find_weaknesses` **正确消费**：既不算短板、也不进 `valid_count`；且与「判定线是 0 分」行为可区分（p25=0 + 得分 0 → `count=0, valid_count=6`；无行 → `valid_count` 少 1） | 探针 rv_probe7 |
| AST 纯净性守卫是否真扫到本模块 | **是**：`tests/architecture/test_domain_purity.py` 用 `DOMAIN.rglob("*.py")` 动态枚举，不是硬编码清单 | 该文件 `:33/:48/:58` |

**Task 7 的问题不在行为，在测试网与文档数字**：见缺陷 C3（分组键 `item` 维度零覆盖）、M3（`age_group` 不校验）、m1（`lookup_p25` 静默取首个匹配行）、m2/m3（两处「实测」数字不成立）、G3（spec §14 #24 的区间不可复现）。

---

## Task 8 独立结论（`derive.py` 逐行阅读的结果）

**`classify_trend` 与 spec §6.3 等价 —— 这是我本轮最重要的一次独立验证，做法与结论：**

我**没有**读 `test_trend_oracle.py::_oracle`，也**没有**读 `derive.py::classify_trend` 的实现来写我的版本。我从 spec §6.3 的表格文字（含两条勘误）自己翻译了一份分类器，并且**连权重表也是自己从 spec §4.2 的表格抄的**（`{bmi:15, vital_capacity:15, sprint_50m:20, sit_and_reach:10, standing_jump:10, pull_up_or_sit_up:10, distance_run:20}`，和 100），总分也自己写 `Σw·s // 100`。然后对 500 人生成数据（零注入、`week1`、两学年按 `SEMESTERS.is_current` 认、龄组按记录所属学年取）逐人分类：

```
paired: 500 500 same set: True
independent-classifier vs trend_label : 500 / 500  mismatches: 0
independent-classifier vs production  : 500 / 500  mismatches: 0
my_total vs national_total            : identical on all 1000 dicts
none totals: 0  cells compared: 7000  cell diffs: 0
label distribution (independent): {'持续下滑': 100, '波动大': 75, '稳定': 200, '稳步提升': 125}
```

这是**第三次**独立对账，结果与前两次一致（500/500）。附带确认：我抄的权重表与 `ITEM_WEIGHTS` 逐字相等；我的 `//100` 总分与生产 `national_total` 在全部 1000 个 dict 上相等；「重新正查」与记录里的 `score_*` 诊断列在两个学年共 7000 格上差异 0；标签分布与配额 `{100,75,200,125}` 逐项相等。

**逐条核对简报 §A 的四个要点：**

| 要点 | 结论 |
|---|---|
| 行序 波动大 → 持续下滑 → 稳步提升 → 稳定 | 正确（`derive.py:226-241`）。**行序变异实测**：把持续下滑提到波动大之前 → `3 failed, 38 passed`，红的是 `test_volatile_outranks_declining`、`test_trend_volatile`、对账测试（`425/500`，**不一致恰为 75 = 波动大配额**）；同一变异下**我的独立分类器仍对 trend_label 500/500**，即 75 人全部被持续下滑吃掉、其余 425 人一个没误伤 —— Ruling 64a 的「可证明不可达」由此第三次得到精确实测证据 |
| 「持续下滑」第二分支是「≥3 项下降 ≥5 分」而非「≥3 项为负」 | 正确（`:233-235` 用 `delta <= -SINGLE_ITEM_DROP` 计数，不是 `delta < 0`） |
| 「波动大」`min(#{d>0}, #{d<0}) >= 3` 且 `d == 0` 两边都不计 | 正确（`:224-229`，`> 0` / `< 0` 严格） |
| 总分阈值作用在「先各自整除再相减」的整数差上 | 正确：`national_total` 用 `// 100`（`:173`），`classify_trend` 只比较调用方传入的两个整数总分。spec §6.3:383 声称的「443 人两种口径差值非零、区间 [−0.90,+0.95]」我**逐字复现**（443/500，[−0.90, 0.95]，均值 +0.0242） |

**其余逐行结论：**

- `national_total`：`Σ ITEM_WEIGHTS[i]·s[i] // 100`，7 项任一为 `None` → `None`，**「键不存在」与「值为 None」同等对待**（用 `scores.get(item)`）——实测 `{6 项}` → `None` ✓。
- `find_weaknesses`：只遍历 `WEAKNESS_ITEMS`（6 项）✓；`score is None or line is None → continue`（两者都不进 `valid_count`）✓；比较符严格 `<` ✓；`dominant_bucket` 的三级决胜（短板数 → 桶内最低分 → `_BUCKET_ORDER` 声明序）与 Ruling 100 一致，`_BUCKET_ORDER` 从 `ITEM_BUCKET` 派生（实测 `['endurance','strength','speed_flexibility']`）✓；`W=0` 时用桶内有效项均值 ✓。
- `flag_body_comp`：两个比较都严格 ✓；`limit` 一律按性别填 ✓；**240 组合穷举**（`body_fat_pct` 8 值 × `muscle_mass_kg` 5 值 × `p20` 3 值 × 2 性别）→ vocabulary 恰为 `{'body_fat_high','muscle_low'}`、顺序固定、`abnormal == bool(reasons)`、`limit` 一律非 None、**0 例外** ✓；签名实测 `['body_fat_pct','muscle_mass_kg','sex','snapshot_muscle_p20']`，无 `smi` ✓。
- `derive`：11 参数、`age_group` 在第 9 位 ✓（`inspect.signature` 实跑）。**一致性校验在 TypeError 安全性上是完备的**——我枚举了「curr 含 None 值 / prev 含 None 值 / 两侧 total 的 None-ness」的全部组合，唯一能走到 `(curr_scores[item] - prev_scores[item])` 的路径必然两侧七项值都非 None；Ruling 106 保留的 `prev_total is not None` 合取项确实承重。
- **形态 6 的零覆盖（Ruling 110）仍然如此，我用变异复现了它的全部后果**（见缺陷 G5）。

---

## 验证过的命令与实测输出

```
$ cd backend; python -m pytest -q                     → 369 passed in 10.25s
$ cd backend; python -m pytest -q -W error            → 369 passed in 10.03s（无警告）
$ cd backend; python -m pytest tests/architecture -q  → 3 passed in 0.02s
$ python -m pytest tests/domain/test_derive.py tests/domain/test_percentile.py --collect-only -q
                                                      → 51 tests collected
$ git diff --stat c72b53f..edf718a -- backend/        → 4 files changed, 1463 insertions(+)
$ git diff --stat c72b53f..edf718a -- backend/app/seed/ backend/data/   → （空）
$ Test-Path backend/pe.db                             → False
$ (Get-ChildItem backend/data/seed -File).Count        → 0
```

**探针（全部写在 `%TEMP%`，直调生产代码）**

| 探针 | 目的 | 关键输出 |
|---|---|---|
| rv_probe1 | 第三次独立 500 人对账 | `500/500 vs trend_label`、`500/500 vs production`、`7000 cells, 0 diffs`、`none totals: 0` |
| rv_probe2 | 24 组常模独立复算 + `compute_snapshot` 边界 | `diffs: 0, inversions: 0`、`P25 dedup [30,40,50,60,62,64]`、n=29→national/30→school、`age_group='18-19'` n=40 不报错、n=5 → `KeyError` |
| rv_probe3 | 替代推导变体 / 重复样本 / ORM 对应 | 每档等占比 P25 去重 = `{45.0, 57.5}`；ORM-only = `{batch_id, computed_on, id, semester_id}` |
| rv_probe4/5/6 | 本校 P25 / 半分 / 样本量 / 常模差的**切片条件搜索**（2 配置 × 6 切片 × 2 龄组约定 × 2 得分来源） | 唯一能复现 Ruling 91 全部数字的条件 = `[缺省注入] × 2025-2026 week16 × score_* 诊断列` → `P25=[50,64] diff=[-7,34] mean=+9.90 n=[106,159] dr=[20,20,30,34]` |
| rv_probe7 | derive 十种输入形态 / 签名 / token 穷举 / find_weaknesses 边界 | 形态 1-9 与账本表格逐条相符；**形态 10（`curr_total=99`）被静默接受**；`lookup_p25` 重复行取首个 |
| rv_probe8 | `years` 符号 / str-enum 哈希 / 形态 6 覆盖 | `years=-1.0` → derive 静默返回 `持续下滑` + `annual_change[national_total]=-10.0`；`years=0.0` → `ZeroDivisionError` |
| rv_probe9 | 变异 RV_C 下形态 6 的静默后果 | `trend=稳步提升`、满 7 键 `annual_change`（`national_total: 10.0`），而真值 `national_total(prev)=None` |
| rv_probe10 | 还原复核 + Task 9 照抄源 staleness | `WeaknessResult(patterns=())` → `TypeError`；`'body_fat_over'` 不在生产 vocabulary |
| rv_probe11 | spec/源码注释里的两个实测数字 | `443/500`、`[-0.90, 0.95]`；`age==20: 132 = 26.4%`、两学年跨组 132 人 |
| rv_probe12 | 逐文件测试数 / 空体测试 / 60 与 66 是否官方档分 | 10 / 41，空体 0 条；60 与 66 在 4 个组的档分阶梯里都存在 |
| rv_probe13/14/15 | **Ruling 102 的探针与后果量化** | 见下「Ruling 102 我建议怎么解」 |

**6 次变异（全部完全还原）**

| # | 变异 | 位置 | 结果 | 实现者/账本声称 | 一致 |
|---|---|---|---|---|---|
| A | 行序反转（持续下滑提到波动大之前） | `derive.py:226-236` | `3 failed, 38 passed`；对账 `425/500`、不一致 **75** | 3 条 / 75 | ✓ |
| B | 去掉方向感知（`lower_is_better = False`） | `percentile.py:124-126` | `3 failed, 7 passed`；失败信息含 `[80,76,74,66,50]`（sprint_50m）与 `p25=72`（distance_run，期望 30） | 3 failed（Task 7 变异 A） | ✓ |
| C | prev 一致性校验改单向（`prev_complete and prev_total is None`） | `derive.py:477` | `1 failed, 40 passed`（`test_derive_rejects_prev_total_without_prev_scores` DID NOT RAISE）；形态 6 静默放行 | 变异 3b：红 1 条 | ✓ |
| **D** | **`derive` 丢弃全部体成分输入**（`flag_body_comp(None, None, sex, None)`） | `derive.py:518` | **`369 passed` —— 0 条变红**；体脂 35%（男阈值 20）+ 肌肉 10kg（P20=40）→ `abnormal=False, reasons=()` | 实现者在关切 9 里**预测**会全绿（未实跑） | ✓ 且已实跑取证 |
| **E** | **`compute_snapshot` 分组键忽略 `item`** | `percentile.py:203` | **`369 passed` —— 0 条变红**；2 项 × 30 行 → 塌成 **1 行** `sprint_50m`、`sample_size=60`、`p25=10.0` | 无人测过 | 新发现 |
| **F** | **`find_weaknesses` 遍历 7 项而非 6 项** | `derive.py:294` | **`369 passed` —— 0 条变红**；给快照补一行 BMI 后同一变异立刻 `ValueError: min() arg is an empty sequence` | 无人测过 | 新发现 |

**还原三重证据（6 次变异后统一复核，未用 `git checkout`）**

```
$ git diff --stat            → （空）
$ git status --short         → （空）
$ Select-String MUTATION_RV（4 个文件）→ Count 0
$ python 读字节              → derive.py   31265 bytes, sha256[:16] 29E6B79A42C971B6, MUTATION_RV 0
                               percentile.py 15127 bytes, sha256[:16] E5E78141A1E72798, MUTATION_RV 0
$ python -m pytest -q        → 369 passed
$ python -m pytest -q -W error → 369 passed
$ python -m pytest tests/architecture -q → 3 passed
$ 行为复核：体脂 35% / 肌肉 10kg(P20=40) → BodyCompFlag(abnormal=True, reasons=('body_fat_high','muscle_low'), limit=20.0)
```
`derive.py` 的 31265 bytes 与账本 :1246 记的 `29e6b79a…ad6c25b6 / 31265` 逐字相符；`percentile.py` 的 15127 与账本 :1058 记的 fix round 1 后长度相符。

---

## 缺陷（按严重度）

### Critical

**C1 — `DerivedResult.body_comp` 在全部 41 条测试里零断言：`derive` 可以静默丢弃全部体成分输入而全量 369 条测试保持全绿**

- **位置**：`backend/tests/domain/test_derive.py`（全文件 `body_comp` 只出现在 `flag_body_comp` 的 7 条单元测试里，**没有一处读 `r.body_comp`**）；被测代码 `backend/app/domain/derive.py:518`。
- **现象（取证）**：变异 D 把 `:518` 改成 `flag_body_comp(None, None, sex, None)` 后 `python -m pytest -q` → **369 passed**。同一变异下的行为实测：
  ```
  体脂率 35%（男阈值 20）、肌肉量 10kg（P20=40） -> abnormal = False reasons = () limit = 20.0
  ```
  还原后同一输入 → `abnormal=True, reasons=('body_fat_high','muscle_low')`。
  Grep 取证：`Select-String -Path tests\domain\test_derive.py -Pattern "body_comp"` 的 19 处命中里，`r.body_comp` / `.body_comp` **0 处**；`tests/` 全目录亦 0 处。
- **后果（会在 Task 9 爆）**：`C` 是 spec §6.2 里 **R1（W≥2 AND C）/ Y2（W=0 AND C）/ Y3（W≥2 AND NOT C）** 三条规则的输入。`C ≡ False` 会让红色层清空、Y2 永不触发、分层分布整体偏移，**而测试全绿、日志无异常**。这正是本项目反复吃亏的缺陷形态。变异形状也很现实：`flag_body_comp` 有 4 个实参，少传/传错一个是常见的转录失误，而 Task 10 还要为 `snapshot_muscle_p20` 传 `None`（Ruling 102），离「四个都传 None」只差一步。
- **历史**：实现者在 `task-8-report.md:555-563`（关切 9）**已经预测了这一点并建议补 2–3 条断言**，但它没有实跑（自称「这是第 5 次变异、超出简报要求」）。Ruling 103 只采纳了「补一条断言 `r.weakness`」的一半，`r.body_comp` 那一半**没有任何裁定记录就消失了**。
- **建议**：在 `test_derive_exposes_weakness_fields` 里（或新增一条）断言体成分透传，输入用我已实跑过的那组：
  ```python
  r = derive(s, None, national_total(s), None, 1.0, 35.0, 10.0, Sex.MALE, LOWER_GRADE, SNAP, 40.0)
  assert r.body_comp.abnormal is True
  assert r.body_comp.reasons == ("body_fat_high", "muscle_low")
  assert r.body_comp.body_fat_pct == 35.0 and r.body_comp.limit == 20.0
  ```
  我实测这组输入在还原后的代码上给出上述全部结果，故这条断言落地即绿、且在变异 D 下必红。
- **置信度**：**高**（变异、行为、grep 三路取证）。

**C2 — `test_bmi_never_counted_as_weakness` 是空转测试：spec §4.2「短板判定项 = 6、W 的分母是 6」失去唯一守卫**

- **位置**：`backend/tests/domain/test_derive.py:250-252`；被测代码 `backend/app/domain/derive.py:294`。
- **现象（取证）**：变异 F 把 `for item in WEAKNESS_ITEMS:` 改成 `for item in tuple(ScoredItem):`（即把 BMI 纳入短板遍历）后 `python -m pytest -q` → **369 passed**。原因：该测试用的 `SNAP = [snap(i, 60) for i in ALL6]` **不含 BMI 行**，于是即使循环覆盖 BMI，`lookup_p25` 也返回 `None` → `continue`，与「BMI 不在循环里」**行为不可区分**。测试断言的 `count == 0` 两种实现都成立。
  进一步取证：给快照补一行 `snap(ScoredItem.BMI, 60)` 后，同一变异立刻以 `ValueError: min() arg is an empty sequence` 响亮失败（因为 `counts` 只有 `None` 桶，而 `_BUCKET_ORDER` 不含 `None` → `tied` 为空 → `min()` 炸）。
- **后果（会在 Task 9 爆）**：spec §14 #18 把这一条的影响面写成「**分层引擎全部规则阈值、R1/R2/Y3 触发率、分层分布**」。BMI 一旦计入 `W`，一个体脂超标学生会同时抬高 `W` 与 `C`，**R1 被系统性过度触发**（spec §4.2 明写要排除的理由），红色层规模虚高。而这个口径现在没有任何有效守卫。
- **建议**：把该测试的快照换成含 BMI 行的版本并加一条 `valid_count` 断言：
  ```python
  SNAP7 = SNAP + [snap(I.BMI, 60)]
  def test_bmi_never_counted_as_weakness():
      curr = {i: 80 for i in ALL6}; curr[I.BMI] = 10
      w = find_weaknesses(curr, SNAP7, Sex.MALE, LOWER_GRADE)
      assert w.count == 0 and w.valid_count == 6 and I.BMI not in w.items
  ```
  （`valid_count == 6` 同时钉住「分母是 6」，这是当前**没有任何测试**断言的量。）
- **置信度**：**高**。

### Major

**M1 — `derive` 只校验 total 的 None-ness、不校验它的值：一个算错的总分可以静默通过**

- **位置**：`backend/app/domain/derive.py:496-509`（curr 侧）、`:474-495`（prev 侧）。
- **现象（取证）**：形态 10 —— `curr_scores` 七项全 80、`curr_total=99`（与 `national_total(curr_scores)=80` 矛盾）→ **静默放行**：
  ```
  10 curr_total=99 (值错但非 None)  -> OK trend=insufficient_data annual_change={} national_total=99 W=0/6
  ```
  `99` 原样进入 `DerivedResult.national_total`（`derive.py:540`）与 `classify_trend` 的 Delta（`:516`）。而 `:507` 的错误消息明写「`curr_total` 必须由调用方用 `national_total(curr_scores)` 算出」——**这句话没有机制支撑**。
- **后果（Task 10 爆）**：Task 10 若写成 `round(Σ/100)`、或漏一项权重、或对缺项做了重归一，则同层内排序（spec §6.1 空洞一的唯一键）与趋势判定（Y4 的唯一输入）**同时**错，且全绿。`derive` 是这条口径的漏斗口，也是唯一能拦住它的地方。
- **建议**：`if curr_complete and curr_total != national_total(curr_scores): raise ValueError(...)`，prev 侧同理。这**不是**第二处加权——它调用的是唯一所有者；docstring 里「本函数不重算（避免同一套加权出现在两处）」的理由因此不成立（成本：每人 7 次乘法）。
- **置信度**：机制**高**（实测）；Task 10 是否真会算错属推测（**中**）。

**M2 — `years` 无任何校验，负值静默反转趋势与全部 `annual_change` 的符号**

- **位置**：`backend/app/domain/derive.py:223`（`(curr_total - prev_total) / years`）、`:529/:532`；入口 `:461-469` 只校验 `age_group` 与七键。
- **现象（取证）**：
  ```
  years=-1.0: OK trend=持续下滑 annual_change[national_total]=-10.0     ← derive 静默接受
  classify_trend(totals 75→70): years=1.0 → 持续下滑 / years=2.0 → 稳定 / years=-1.0 → 稳定
  years=0.0 → ZeroDivisionError（响亮，可接受）
  ```
- **后果（Task 10 爆）**：`years` 由 Task 10 从两个学年（或两个日期）相减得到。减法方向写反 → `years = -1` → **每个学生的趋势翻面、7 个 annual_change 全部变号**，且不报错。本项目已经被同型缺陷咬过一次（Ruling 62 / 评审 M5：生成器把趋势符号接反，两类标签整体互换，活过两轮 236 条测试）。`age_group`（11 个参数里另一个自由量）已经在 Ruling 107 下加了 fail-fast，`years` 没有。
- **建议**：`derive` 入口加 `if years <= 0: raise ValueError(...)`（与 Ruling 107 同理）。顺带解决 G1：`years` 的语义（该不该年化）一旦被裁定，这条校验就是它的执行点。
- **置信度**：机制**高**；触发概率**中**。

**M3 — `compute_snapshot` 不校验 `age_group`：Ruling 107 的守卫只加在消费者一侧，生产者一侧是同型的静默路径**

- **位置**：`backend/app/domain/percentile.py:201-204`（`Sex(...)` 与 `ScoredItem(...)` 都做了转换校验，**只有 `row["age_group"]` 原样入键**）。
- **现象（取证）**：
  ```
  age_group='18-19' with n=40 -> NO ERROR, rows: [('18-19', 23.25)]
    lookup_p25 with legal group on that snapshot -> None
  age_group='18-19' with n=5  -> KeyError ('sprint_50m', 'male', '18-19')
  ```
- **后果（Task 10 爆）**：这与 Ruling 107 描述的缺陷形态**逐字相同**（「非法组名会让 `lookup_p25` 一行都匹配不上 → `valid_count=0 < 4`，整批学生静默走进不分层闸门」），差别只在责任方：Ruling 107 堵的是消费者传错，这里堵不住**生产者写错**。样本 ≥30 时（500 人下四组都是 106/119/156）走的是静默路径；样本 <30 时反而因为要查常模而 `KeyError`——**同一种输入错误，响不响亮取决于样本量**，这比一律静默更难查。
- **建议**：`compute_snapshot` 入口对 `age_group` 做与 `derive` 同一条 `AGE_GROUPS` 校验（`AGE_GROUPS` 已是全仓唯一口径，不引入第二份）；或至少像 Ruling 88 处置 `student_id` 那样在 docstring 里明写调用方职责。
- **置信度**：**高**。

**M4 — Ruling 63「加权求和只能有一个所有者」在字面上不成立：`app/seed/fitness.py` 里的第二份实现仍在**

- **位置**：`backend/app/seed/fitness.py:143-156`（`_weighted_total`），消费者 `fitness.py:842`、`:857`、`tests/seed/test_trend_oracle.py:23/92/433`。
- **现象（取证）**：
  ```python
  return sum(ITEM_WEIGHTS[item] * score for item, score in scores.items()) // 100
  ```
  它自己的 docstring（`:146`）写着：「**Task 8 会提供生产版 `national_total`，届时本函数应删除并改用它**（Ruling 63：加权求和只能有一个所有者）」。Task 8 已结案（`edf718a`），**函数仍在，且没有任何裁定记录它为何保留**。Grep 全仓 `_weighted_total` → 16 处命中，其中 3 处在 `app/seed/fitness.py`（生产路径）。
  另：它迭代 `scores.items()`，**既不做 None 判定也不做键齐全判定**——传 6 项会静默给出按权重和 85 算的总分（`national_total` 在同样输入下返回 `None`）。
- **后果**：`//100` 或权重口径若变，两处要同时改；漏改的那一处会让「生成侧的 trend_label 真值」与「判定侧的分类」在不同口径上比较——而 500 人对账测试是这两者之间**唯一**的连接点，它用的是 `_weighted_total`（oracle 侧）对 `national_total`（生产侧），所以口径一旦分岔，对账会红，这算是不幸中的有幸。真正的风险是「静默 6 项」那一条。
- **建议**：请控制者裁定二选一并记账：(a) 删掉 `_weighted_total`、`fitness.py` 与 `test_trend_oracle.py` 改用 `national_total`（`app.seed → app.domain` 方向合法，不改三个 CSV，故哈希不受影响）；(b) 明确保留为 seed 侧私有实现，但给它补一条「7 键齐全」的前置断言，并在账本里把 Ruling 63 的措辞从「唯一所有者」改成「domain 层唯一所有者」。
- **置信度**：**高**（代码与 docstring 都在仓里）。

**M5 — `stratification_result.percentile_source` 没有生产者，且「该组一行快照都没有」时它无定义，而列是 NOT NULL**

- **位置**：`backend/app/db/models.py:436`（`PERCENTILE_SOURCES = {"school","national"}`）、`:450`（`percentile_source: Mapped[str]` → 不可空）、`:454-461`（CHECK）；`backend/app/domain/derive.py:134-151`（`DerivedResult` 无此字段）、`backend/app/domain/derive.py:94-110`（`WeaknessResult` 无此字段）。
- **现象（取证）**：`PercentileRow.source` 存在且取值域与 ORM 同域，但 `find_weaknesses` 查到行之后**只取 `p25`**（`percentile.py:252-254`），`source` 在 domain 层的输出里被丢掉。dataclass 字段实测：`WeaknessResult: ['items','count','valid_count','dominant_bucket']`、`DerivedResult: ['sex','trend','weakness','body_comp','annual_change','national_total']` —— 两者都不带 `source`。
- **后果（Task 10 爆）**：Task 10 要写这一列，只能自己再扫一遍快照去反查 `source`；而当某 (项, 性别, 年级组) **一行都没有**时（`lookup_p25` 全返回 `None` → `valid_count = 0` → 该生 `insufficient_data`），`percentile_source` **无值可写**，而列不可空且有 CHECK → 要么 `IntegrityError`，要么 Task 10 自己编一个值（编 `school` 会让研究侧误以为这一批用的是本校线）。这是 Ruling 102 的同型缺口（硬规矩 #10：「凡 spec 里出现一个查表得到的量，必须当场追问它的生产者是谁」）。
- **建议**：`WeaknessResult` 加 `percentile_source: str | None`（`find_weaknesses` 已经握着那些行，零额外查表成本；混源时裁定一个口径，例如「任一项为 national 即 national」），并裁定 `valid_count = 0` 时写什么（列改可空，或给域加第三值）。
- **置信度**：**高**（ORM 与 dataclass 字段均已实测比对）。

**M6 — 计划 :1668-1671（Task 9 Step 1 的 `mk()`）仍是 Ruling 98 / 97① 之前的形状，逐字照抄必然失败**

- **位置**：`Document/2026-09-28-实施计划01-数据基座与分层引擎.md:1668-1669`（`WeaknessResult(..., patterns=())`）、`:1670-1672`（`reasons=("body_fat_over",)`）。
- **现象（取证，实跑）**：
  ```
  WeaknessResult(patterns=()) -> TypeError: WeaknessResult.__init__() got an unexpected keyword argument 'patterns'
  BodyCompFlag(reasons=('body_fat_over',)) -> 构造成功（无 vocabulary 校验）: ('body_fat_over',)
  生产 token vocabulary: ['body_fat_high', 'muscle_low'] -> 'body_fat_over' 在其中吗: False
  ```
- **后果（Task 9 爆）**：`mk()` 是 Task 9 全部 12+ 条规则测试的构造入口，`patterns` 那一处会让它们**在构造阶段就全部炸掉**；`body_fat_over` 那一处更阴——它能构造成功，于是 Task 9 的 `explain()` 测试会拿一个**生产上永不出现的 token** 去验文案，`explain()` 对真 token 的渲染反而零覆盖。这是硬规矩 #11（「改一处规格/签名时必须在同一份文档里 grep 它的全部照抄源」）的**第三次**发生（前两次：Ruling 105 片段 `NameError`、Ruling 109 五处 10 参数调用），也是第一次跨任务边界。
- **建议**：派 Task 9 之前把这两行改成 `WeaknessResult(items=(), count=w, valid_count=valid, dominant_bucket=dominant)` 与 `reasons=("body_fat_high",) if c else ()`；同时 grep 一遍 Task 10/11 节里对 Task 7/8 符号的引用（我已查过：Task 10 节是散文描述、无 `derive(` 片段，暂无同型问题）。
- **置信度**：**高**。

### Minor

**m1 — `lookup_p25` 静默返回首个匹配行，重复组行时结果依赖列表顺序**
`percentile.py:252-254` 是线性扫描 + `return` 首命中。实测：同一 `(item,sex,age_group)` 放两行（p25=60 与 p25=10），得分全 30 → 顺序 `[60,10]` 得 `count=6`、顺序 `[10,60]` 得 `count=5`。ORM 的唯一键是 `(semester_id, computed_on, item, sex, age_group)`（`models.py:382-389`），**库里天然可能有多日多行**；`find_weaknesses` 的 docstring 只写「snapshot 由调用方注入」，没写「每组只能一行」。建议：docstring 补前置条件，或重复时 `raise`。置信度：高（机制实测），触发需要调用方失误（中）。

**m2 — `percentile.py:104-105` 与计划 :1141 的「每档等占比 → P25 对所有项都退化成同一个 57.5，实测确认」不成立**
两种自然实现（对 20/15 个档的得分列表取 `np.percentile(...,25,"linear")`，去重与不去重）下，24 组的 P25 去重取值都是 **{45.0, 57.5}**：22 组 57.5，而 `pull_up_or_sit_up male` 两组是 **45.0**（该组只有 15 个档，`0.25×14=3.5` 落在 40 与 50 之间）。结论（丢掉项别信息）仍成立，但「同一个 57.5」与「实测确认」不准确。置信度：高。

**m3 — 账本 :1030 给 Task 8 的前向约束「p25 可能是半分（实测 24 组里 1 组 = 60.5）」不成立**
我在 16 个切片组合（2 注入配置 × 6 单切片 + 4 合并）上实测：**没有一个**切片是「恰好 1 组 = 60.5」。含 60.5 的切片都另有半分（零注入 `2025-2026 week16` = 60.5 + 61.5；`2024-2025 week1` = 60.5 + 62.5）；恰好 1 行半分的切片其值是 62.5 / 52.5 / 57.5 / 63.5。实测到的半分值集合是 `{52.5, 57.5, 60.5, 61.5, 62.5, 63.5}`。**「p25 可能是半分」这个结论成立**（Task 8 也正确地按半分处理了），只是那个具体数字与「24 组里 1 组」不成立，且未带切片条件（硬规矩 #8）。置信度：高。

**m4 — `test_one_zero_delta_makes_volatile_unreachable`（test_derive.py:109-115）是负断言，比它的 oracle 双胞胎弱**
它只断言 `!= Trend.VOLATILE`；该输入的实测真实结果是 `稳定`。`tests/seed/test_trend_oracle.py:381-382` 的同一用例**同时**断言了 `!= "波动大"` 与 `== "稳定"`。若实现改判成 `持续下滑`（例如第二分支的阈值写错），生产侧这条仍绿。建议改成 `== Trend.STABLE`。置信度：高。

**m5 — `test_national_norm_covers_every_weakness_item_sex_and_grade_group`（test_percentile.py:65-70）只断言三个回显字段**
`assert r.source == "national" and r.item is item and r.sex is sex` —— 不断言 `age_group`、不断言任何百分位值。它的真实价值是「24 个 (项,性别,年级组) 组合在表里都存在、都不 KeyError」，这是有价值的冒烟测试，但名字里的 "covers" 容易被读成「值也被覆盖了」。值的覆盖由相邻的 monotone 那条提供。置信度：高。

**m6 — `annual_change` 的键序无守卫**
账本 :1163 把插入序 `vital_capacity, sprint_50m, sit_and_reach, standing_jump, pull_up_or_sit_up, distance_run, national_total` 记为实测事实（我复现一致），但 `test_derive_annual_change_covers_six_items_plus_total:431` 用的是 `set(r.annual_change)`。若 Task 9 的 `explain()` 按迭代序渲染「各项年均变化」，这个顺序就成了事实契约而无守卫。建议：该断言改成 `list(r.annual_change) == [...]`（1 行）。置信度：高（无守卫是事实），是否承重取决于 Task 9（未知）。

**m7 — 仓内没有 `ScoredItem → 中文项目名` 的映射，而 Task 9 的 `explain()` 必须要它**
Grep `1000 米|800 米|肺活量|坐位体前屈|立定跳远|引体向上` 于 `backend/app/` → 29 处命中**全是注释**，没有一张映射表。spec §9.2:634 的示例文案是「你的 **1000 米跑与引体向上** 在校内同龄男生中低于 P25」，且项目名**随性别变**（1000/800 米、引体向上/仰卧起坐）。Task 9 只能自己造，那是 spec §4.2 表格的第三份手抄（前两份：`ITEM_BUCKET` 的注释、`seed/fitness.py::COLUMN_BY_ITEM`）。建议：在 Task 9 派单里指明出处（spec §4.2 表）与性别依赖，或让它落在 `indicators.py` 而不是 `stratify.py`。置信度：高（映射不存在是事实）。

---

## 报告数字复核表

| 声称 | 出处 | 我的实测 | 一致 |
|---|---|---|---|
| 369 passed | 账本 :1233 | `pytest -q` 369 passed（10.25s / 10.06s / 10.23s 三次） | ✓ |
| `-W error` 同样 369、洁净 | 账本 :1233 | 369 passed in 10.03s，无 warning | ✓ |
| `tests/architecture` 3 passed | 账本 :1124 | 3 passed in 0.02s | ✓ |
| Task 7 的 10 条 + Task 8 的 41 条 = 51 | 账本 :1072/:1280，计划 :1160/:1624 | `--collect-only` 51 collected；逐文件 `^def test_` = 10 / 41；空体测试 0 条 | ✓ |
| 24 组常模**逆序 0 组** | 账本 :999，报告 :149 | 独立实现复算 24×5=120 值全等，逆序 0 组 | ✓ |
| 国标 P25 去重 `{30,40,50,60,62,64}` | 账本 :999，spec §14 #24 | `[30.0,40.0,50.0,60.0,62.0,64.0]` | ✓ |
| `distance_run` 男两组 P25 = 30.0 | 账本 :999/:1013 | `[30.0, 30.0]` | ✓ |
| **500 人对账 500/500** | 账本 :1126/:1281 | 第三次独立对账 **500/500 vs trend_label**、**500/500 vs 生产**；分布 `{持续下滑:100, 波动大:75, 稳定:200, 稳步提升:125}` = 配额 | ✓ |
| 「重新正查 vs 诊断列 3500 格、差异 0」 | 账本 :1126 | 我比了**两个学年共 7000 格**，差异 0（3500 = 单学年 7×500） | ✓（口径不同、结论同） |
| `derive` 11 参数、`age_group` 第 9 位 | 账本 :1183/:1246 | `inspect.signature` → 11 个，`age_group` 第 9 位 | ✓ |
| 六种输入形态行为表 | 账本 :1237-1244 | 1/2 放行（`INSUFFICIENT` + `{}`）、3/4/6 `ValueError`、5 `KeyError`（先于一致性校验）；形态 3 的消息不再撒谎 | ✓ |
| 形态 7（非法组名 + 缺键）先报 `age_group`、消息含合法清单 | 账本 :1265 | `ValueError`，消息含 `['大一、大二', '大三、大四']` | ✓ |
| `annual_change` 7 个键序 | 账本 :1163 | 逐字相同 | ✓（但无守卫，见 m6） |
| `reasons` token vocabulary | 账本 :1164（80 组合） | **240 组合**穷举 → 恰 `{body_fat_high, muscle_low}`、顺序固定、0 例外 | ✓（组合数不同） |
| 变异 1 行序反转 → 红 3 条、不一致 = 75 | 账本 :1131 | 3 failed / 38 passed；425/500，不一致 **75** | ✓ |
| Task 7 变异 A 去方向感知 → 红 3 条 | 报告 :265，账本 :1001 | 3 failed / 7 passed；`[80,76,74,66,50]` 与 `p25 72≠30` 与 docstring `:97`、测试注释 `:87` 逐字相符 | ✓ |
| 变异 3b → 红 1 条；形态 6 静默产出 `稳步提升` + 满 7 键 | 账本 :1251/:1257 | 1 failed / 40 passed；`稳步提升` + `annual_change` 7 键、`national_total: 10.0` | ✓ |
| 「443 人两种口径差值非零、区间 [−0.90,+0.95]」 | spec §6.3:383，`derive.py:18` | **443/500**，区间 **[−0.90, 0.95]**，均值 +0.0242 | ✓ |
| 「age==20 的 132 人 = 26.4%」 | `test_derive.py:200`，账本 :1224 | 年龄分布 `{18:132, 19:143, 20:132, 21:80, 22:13}`；age==20 → **132 = 26.4%**；两学年跨组人数同为 132 | ✓ |
| 「60 与 66 都是官方档分」 | 账本 :1093，测试注释 :372 | 两项 × 两性别的档分阶梯都含 60 与 66 | ✓ |
| 0/24 组触发降级 | 账本 :999，spec §14 #24 | 16 个切片组合全部 `degraded=0`；最小组样本量 39（缺省注入 / `2024-2025 week8`） | ✓ |
| **本校 P25「同一 `2025-2026 week1` 切片上 50–64」** | spec §14 #24，账本 :999，计划 :1141 | week1 实测 **50–63**（零注入）/ **50–62**（缺省注入）；**64 只出现在 week8 与 week16** | **✗** |
| **「跨 7 个切片全距 40–64」** | spec §14 #24，计划 :1141 | 40 只在**不按 Ruling 56 调整上学年年龄**时出现；按 Ruling 56 时全距是 **50–66** | **✗** |
| **Ruling 91「逐组差 −7…+34、均值 +9.90、`distance_run` +30/+34/+20/+20」** | 账本 :1018，spec §14 #24，计划 :1145 | 数字**逐字复现**，但唯一条件是 `[缺省注入] × 2025-2026 week16 × score_* 诊断列`；同切片零注入是 −12…+34 / +9.75，week1 是 −14…+33 / +4.40 | **△ 数字对、切片条件从未写下** |
| **「本校 n = 106…159」** | 账本 :999 | 学生级实测 106 / 119 / 156；**159 只在上面同一条件（含 duplicate 行）下出现** | **△ 同上** |
| **「p25 半分：24 组里 1 组 = 60.5」** | 账本 :1030 | 无切片成立；实测半分值集合 `{52.5,57.5,60.5,61.5,62.5,63.5}` | **✗**（结论成立） |
| **「每档等占比 → 所有项同一个 57.5，实测确认」** | `percentile.py:104-105`，计划 :1141 | 去重 **{45.0, 57.5}**；`pull_up_or_sit_up male` 两组 = 45.0 | **✗** |
| Task 7 变异 B（`<`→`<=`）1 failed / 变异 C 2 failed | 报告 :292/:311 | **未复跑**（我用 n=1/28/29/30/31 直接实测边界，等价且更强：29→national、30→school） | 未验 |

---

## 规格与裁定本身的问题

**G1（需要裁定）— spec §6.3③ 自相矛盾：`Delta` 到底除不除以 `years`？账本里没有任何 Ruling 处理过它。**
spec §6.3:370 写「按国标得分计算**年均变化率**」，而 :376-381 的公式块写的是 `Delta = national_total(curr) − national_total(prev)`，**没有 `/years`**。实现（`derive.py:223`）与计划 :1189 取「年均」（除以 years）。`years = 1.0` 时两者等价，所以 500 人对账与全部 41 条测试**都测不出差别**；分岔只在 `years ≠ 1` 时出现，实测：
```
totals 75 → 70（整数 Delta = −5）：years=1.0 → 持续下滑；years=2.0 → 稳定
```
即 spec 字面公式在 years=2 时判 `持续下滑`，实现判 `稳定`。Grep 账本 `years|年均` → 只命中 Ruling 99（讲 `annual_change` 的值），**没有一条裁定处理 `Delta` 的年化**。这必须裁：它决定 Task 10 传 `years` 的语义（跨两学年的比较该不该被年化），也决定 M2 那条校验写成 `years <= 0` 还是别的。我的倾向：**保留实现的「年均」口径**（它与 spec 正文的「年均变化率」、与 `annual_change` 的口径、与 `test_derive_years_scales_the_annual_change` 三者自洽），**回改 spec §6.3 的公式块**加上 `/years`，并记一条 Ruling。

**G2（需要回改 spec）— spec §6.2 的决策表在「自上而下、命中即停」语义下，末行 `valid_count < 4` 对 `W=0 ∧ ¬C` 的学生不可达。**
表末行是 `— | valid_count < 4 | insufficient_data`，而它上面一行是 `G1 | W=0 AND NOT C | green`。一个 `valid_count = 3`、`W = 0`、`C = False` 的学生按「自上而下、命中即停」会先命中 G1 变**绿**，永远走不到末行——而 §6.3①:358 与 §14 #13 明写「`valid_count < 4` 者本日不分层，标记 `insufficient_data`」。**这与 Ruling 64a 是同一类构造性缺陷（决策表里的不可达行）。** 计划 :1745 已经把它修对了（「先判 `valid_count < MIN_VALID_COUNT` → 直接返回 INSUFFICIENT」，并用 `test_insufficient_data_beats_all_rules` 钉住），但**spec 正文没改、也没有 Ruling 记录这次修正**。建议回改 spec §6.2：把闸门行提到表首，或在表下加注「本行优先于全部规则」。附带一条给 Task 9/10：该状态下 `hit_rules` 是空元组，而 `models.py:445-448` 把 `hit_rules` 定义为 NOT NULL 的逗号分隔串、且注释说「最后一项为命中者」——空串会让那句注释为假，值得一并裁定。

**G3（需要回改 spec）— spec §14 #24 里两个已提交的区间都不可按其标注的切片复现。**
见数字复核表的三行 ✗/△。要点：① `2025-2026 week1` 上是 **50–63**（零注入）/ **50–62**（缺省注入），**不是 50–64**；② 全距里的 **40** 只在违反 Ruling 56（上学年记录按学生**本学年**年龄分组）时出现，按 Ruling 56 时全距是 **50–66**；③ Ruling 91 的 `−7…+34 / +9.90 / distance_run +30/+34/+20/+20` 我**逐字复现了**，唯一条件是 `[缺省注入] × 2025-2026 week16 × 用 score_* 诊断列` —— 三份文档（spec、计划 :1145、账本 :1018）都没写这个条件，而 Ruling 90 刚刚因为「漏写切片条件」立了硬规矩 #8。**这是硬规矩 #8 的第二次发生，且发生在这条规矩被写下来之后。** 影响面：#24 是要交给项目负责人裁决的待确认项，它的证据（「与本校 P25 同量级，作为兜底可比」）建立在两个不可复现的区间上。实质结论仍成立（我校到的所有切片本校 P25 都在 50–66、常模 30–64，同量级；常模系统性更宽松、`distance_run` 差 +20…+34 也都复现），但**数字必须带条件重写**。

**G4（已核实，需要裁定）— Ruling 102 成立，我建议的解法见下节。**
独立核实：`compute_snapshot` 传 `'muscle_mass_kg'` → `ValueError: 'muscle_mass_kg' is not a valid ScoredItem`；`percentile.py` 全文 0 处 "muscle"；`PercentileSnapshot.__table_args__` 只有 `source` / `sex` 两个 `_in_domain` CHECK，**`item` 没有**（即「库里存得下、算不出来」的不对称确认无误）；`percentile.py:31` 的注释仍写着「20 是体成分维度 C 的肌肉量判定线」——**一句指向不存在生产者的注释**。

**G5（已核实，建议改裁定）— Ruling 110 把形态 6 的守卫测试推到 Task 10 派单，但坑在 `derive` 里。**
我用变异 C 独立复现了 Ruling 110 的全部实测后果：单向校验下形态 6 静默放行 → `trend=稳步提升` + 满 7 键 `annual_change`（`national_total: 10.0`），而它的基准 70 是 `national_total(prev)` **永远算不出**的值（真值 `None`）；唯一变红的是形态 4 那条（`1 failed, 40 passed`）。**形态 6 至今仍零覆盖**（`test_derive.py` 里名字含 `prev` 的三条分别是形态 3 / 5 / 4，无一是形态 6）。裁定的理由是「Task 10 是 `derive` 的调用方，测试放在消费者一侧最自然」——但坑在被测函数里，把它推到消费者一侧意味着 **Task 9 与 Task 10 期间 `derive` 自己仍然无守卫**，而 Task 9 的测试会直接构造 `DerivedResult`（不经 `derive`），所以那条测试在 Task 9 期间也不会被写到。建议：这条测试 2 行，就在本轮补进 `test_derive.py`；Task 10 派单里保留「不得自行算总分」的约束即可。

**G6（已核实，无需裁定，仅记录）— Ruling 98 删掉 `patterns` 不影响 Task 9 的 `explain()`。**
spec §9.2:634 的示例文案「红色层 ← 你的 1000 米跑与引体向上在校内同龄男生中低于 P25，且体脂率 22.4% 超过男生 20% 阈值」需要四个素材：项目名（`WeaknessResult.items` ✓，但需要 m7 那张中文映射表）、「低于 P25」（泛称 ✓）、「22.4%」（`BodyCompFlag.body_fat_pct` ✓）、「男生 20% 阈值」（`BodyCompFlag.limit` ✓）。**四个都能从现有字段渲染出来**，`patterns` 确实没有消费者。删除是对的。（§9.2 「我的数据」页的雷达图参照线要 P25/P50 数值，那是 API 层从 `percentile_snapshot` 直接读，不经 `explain()`。）

---

## Ruling 102 我建议怎么解

**先给后果的量化（我实跑的，不是推理）** —— 零注入配置、`2025-2026 week1`、肌肉量 P20 按「每个学生最近一次测量」的学生级口径算、分层按 spec §6.2（闸门在前）：

```
肌肉量 P20：female 大一、大二 n=119 P20=23.46 | female 大三、大四 n=106 P20=23.90
            male   大一、大二 n=156 P20=33.40 | male   大三、大四 n=119 P20=33.86
C=True 有肌肉量线: 226/500 (45.2%)   C=True 只看体脂率: 160/500 (32.0%)
因缺线而 C 从 True 翻 False 的学生: 66（13.2%），其中 66 人**只靠 muscle_low** 成立
reasons 分布: () 274 | body_fat_high 126 | muscle_low 66 | 两者 34
W 分布: {0:258, 1:92, 2:77, 3:35, 4:19, 5:11, 6:8}

有肌肉量线的分层: red 100 (R1 89 + R2 11) | yellow 235 (Y1 92 + Y2 93 + Y3 50) | green 165
肌肉量线缺失时  : red  85 (R1 71 + R2 14) | yellow 215 (Y1 92 + Y2 58 + Y3 65) | green 200
降级移动: red(R1) → yellow(Y3) 15 人 | yellow(Y2) → green(G1) 35 人 | red(R1) → red(R2) 3 人（共 53 人换层/换规则）
```
（缺省注入下同向：62 人的 C 翻面。我的 `layer()` 未含 Y4，因为 Y4 只把绿升黄、两列同向偏移，不改变结论。）

**所以后果不是「少一个 token」，而是：约 13% 的学生 `C` 被静默判假，其中 15 人从红（高强度复合干预）降到黄（中等强度），35 人从黄降到绿（维持与兴趣拓展），红色层占比从 20.0% 掉到 17.0%、绿色从 33.0% 涨到 40.0%。** 而被降级的正是 spec §6.1 空洞三**特意要收进来**的那类人（体脂正常、肌肉量不足的瘦弱学生）。附带一条给 Task 11：spec §14 #12 的目标分布是红 20 / 黄 45 / 绿 35，有线时实测 20.0 / 47.0 / 33.0（贴合），缺线时 17.0 / 43.0 / 40.0（绿超 5 个点）——`test_target_layer_distribution_within_tolerance` 的容差是按哪一个校准，必须在 Task 10 之前定。

**我的建议：采 (B) 的最小风险变体，并同时裁定三条配套口径。** 反对 (A)（污染 `ITEM_WEIGHTS` / `WEAKNESS_ITEMS` / `ITEM_BUCKET` 与全部查表逻辑）、反对 (C)（上面 53 人的代价，且让 `muscle_low` 与它的测试成为死代码、与 spec §6.3② 字面不符）、反对 (D)（违反 spec §4.0 的物化要求，分层结果不可复现）。

具体：

1. **不动 `ScoredItem`。** 在 `percentile.py` 里加一个显式的快照指标域，例如 `class SnapshotMetric(str, Enum)`，成员 = 7 个 `ScoredItem.value` + `MUSCLE_MASS_KG = "muscle_mass_kg"`；`PercentileRow.item` 与 `compute_snapshot` 的分组键改用它。ORM 侧**不需要改**（`item` 已是 `String(32)` 且没有 `_in_domain` CHECK——我实测确认过约束清单）。
2. **顺手把 `item` 的取值域约束补上。** 现在 `item` 是 `percentile_snapshot` 里**唯一**没有 CHECK 的业务列（`source` 与 `sex` 都有），这正是 Ruling 102 里「库里存得下、算不出来」的机制来源。补 `_in_domain("item", {m.value for m in SnapshotMetric}, ...)` 能把这个不对称关掉。
3. **降级分支按指标分流：没有国标表的指标不产出该行，而不是编一个常模。** 肌肉量没有国标评分表（`segment_thresholds` 会 `KeyError`），也**不存在**可推导的常模（InBody 的 P20 是设备与人群特异的），所以 `MIN_SAMPLE` 兜底对它只能是「无线可给」——`flag_body_comp` 收 `None`、该支不成立，这与 `lookup_p25` 返回 `None` 的既有语义同构，也符合 Ruling 21「缺测不当最坏值」。**但要留痕**：`source` 域只有 `school`/`national`，无法表达「因样本不足而没有这一行」，所以要么让 Task 10 在 `daily_sync_run` 的统计里计一条「肌肉量 P20 缺线组数」，要么给 `reasons` 加第三个 token（那要先改 spec §6.3②，Ruling 97① 冻结了 vocabulary——需要一条新裁定）。**我实测这个分支在 500 人下不会被触发**：4 组的 n 是 106/119/156/119（缺省注入下 103/111/114/148），全部远高于 30，`0/4` 组降级；按行池化（每人 6 次测量）则是 636/714/905/936。所以留痕是保险，不是常态——这也意味着账本 :1141 说的「需要实跑数据才知道 500 人下各组的肌肉量分布长什么样」这个前置条件，**现在已经跑过了**（硬规矩 #1 已满足）。
4. **必须裁定样本单位：学生 还是 测量行。** `body_comp` 每人有 **6 条**（`measured_on` 不同，实测 3000 行 / 500 人）。按行池化 → n=636…936、male 大一、大二 P20 = 33.10；按「每人最近一次」→ n=106…156、同一组 P20 = 33.40。**两者不同**，而 P20 就是 `C` 的判定线。这与 Ruling 88 给 `compute_snapshot` 定的「每个 (学生, 项目) 只能一行」是同一件事，必须在 Task 10 派单里为体成分重述一遍（建议：**每个学生取 `computed_on` 之前最近一次**，与快照的「哪一天」语义对齐），否则测量次数多的学生会在判定线里被重复计票。
5. **必须喂清洗后的值。** 缺省注入下 `body_comp` 里有 `muscle_mass_kg = 135.0` 这种物理不可能值（unit_error/outlier 注入）与 132 条 `None`。高侧离群对 P20 影响很小（实测 33.10 → 33.00），但**低侧的单位错误会直接把判定线拉低**，让 `muscle_low` 系统性少判——与 `score_item` docstring `:134-139` 讲的低侧夹取风险同型。

---

## 值得肯定的地方（只写我验证过的）

1. **`classify_trend` 真的等价于 spec §6.3。** 我从 spec 正文（含两条勘误）自己翻译了一份分类器、连权重表都自己从 §4.2 抄，对 500 人逐人对账得 **500/500 vs `trend_label`** 与 **500/500 vs 生产实现**；在行序变异下我的分类器仍对 `trend_label` 500/500，而不一致数精确等于 **75 = 波动大配额**。这是三份独立实现在同一批数据上完全对齐，Ruling 64a/64b/69 的守卫体系是真的成立的。
2. **`national_norm` 的推导经得起独立复算。** 我不看实现、按 Ruling 84 的假设重写了一遍，24 组 × 5 档 = **120 个值逐值全等**、逆序 **0** 组、P25 去重 `{30,40,50,60,62,64}`。方向感知有 3 条独立守卫（变异 B 红 3 条），且 docstring `:97` 的 `[80,76,74,66,50]` 与测试注释 `:87` 的「50/30 → 74/72」都与我的实测**逐字相符**——这两处不是凭推理写的。
3. **`derive` 的一致性校验在 TypeError 安全性上是完备的。** 我枚举了 curr/prev 的 None 值与两侧 total 的 None-ness 的全部组合，唯一能走到减法的路径必然两侧七项值都非 None；Ruling 106 保留的 `prev_total is not None` 合取项确实承重（实现者在关切 E 里对「不确定裁定结果时选兼容性更强的一侧」的判断是对的）。
4. **`lookup_p25` 的 `None` 语义被正确消费，且与「判定线是 0 分」可区分。** 实测：p25=0 + 得分 0 → `count=0, valid_count=6`；无快照行 → 该项既不算短板也不进 `valid_count`；半分判定线 57.5 下得分 57 算短板、58 不算（严格 `<`，spec §14 #21）。
5. **控制者写进 spec 与源码注释的两个实测数字我逐字复现了**：`443/500` 与 `[−0.90, +0.95]`（spec §6.3:383、`derive.py:18`）、`132 人 = 26.4%`（`test_derive.py:200`）。不是所有数字都错——错的集中在「本校 P25 区间」这一族（G3/m3），根因是同一个：漏写切片与口径条件。

---

## 无法判断的事项

1. **M1 / M2 / M3 / M5 的触发概率。** 机制我都实测了，但它们都要等 Task 10 的调用代码存在才知道会不会真被踩到。我没有跑任何 Task 10 路径（它还不存在）。
2. **Ruling 91 那次探针到底用了哪个切片。** 我是用 2 配置 × 6 切片 × 2 龄组约定 × 2 得分来源的搜索**反推**出唯一能复现的条件（`[缺省注入] × 2025-2026 week16 × score_* 诊断列`）。若控制者手里还留着那次的命令或输出，一比对即可确认；我不能排除还有第五个维度（例如某个我没试的合并切片）也能给出同样的数。
3. **Task 7 的变异 B（`<`→`<=`，报告称 1 failed）与变异 C（`< MIN_SAMPLE - 1`，报告称 2 failed）我没有复跑。** 我用 n=1/28/29/30/31 直接实测了 `MIN_SAMPLE` 边界（29 → `national` 且 `sample_size=29`、30 → `school`），这比复跑变异更直接，但报告里那两条的红条数我没有独立确认。
4. **写盘事故（账本记的第 10 / 12 次工具与磁盘分歧）无法回溯验证。** 我只能确认当前磁盘字节与 git 一致（`git diff --stat` 空 + SHA256 与账本记的值相符）。本轮我自己**没有**遇到写盘分歧：6 次 `SearchReplace` 全部正常落盘（每次都用 python 读字节确认了 marker 计数与字节数变化）。
5. **`derive.py` 541 行该不该拆。** 我没有可执行的判据，只能确认它比 `generate.py` 大、且承载 5 个导出符号 + 8 个常量 + 1 个私有校验函数。账本已把它列为延后 Minor，我同意留给终审。
6. **`percentile.py` 全 bare LF 而源码全 CRLF 的影响。** 账本 :1056 已记为延后 Minor 并给了「终审前不要跑 `git add --renormalize`」的纪律；我没有验证这条纪律之外的后果，也刻意没有跑任何 `git add`。
