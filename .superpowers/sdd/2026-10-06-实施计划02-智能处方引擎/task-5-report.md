# Task 5 实现者报告 —— 处方装配（简化版）：intensity + assembler + safety + override

> **代码基线** `c8e26b8`（分支 `feature/plan-02-prescription-engine`）。
> **本 Task 的 5 个 commit**：`d78120a`（5.1）→ `1c5b9bb`（5.2）→ `5f05dda`（5.3）→
> `14673aa`（5.4）→ `fc8f5a8`（5.5）。**未 push、未切分支、未碰 main。**
> **一句话结论**：4 个生产模块 + 4 个测试文件落地，全量 **592 → 672 passed**，
> `app/domain/` 分支覆盖 **888 stmts / Miss 0 / 260 branch / BrPart 0 / 100%**，
> 两份架构守卫全绿且**一个字都没改**，公开面 **24 → 43**，扫描面 **28 → 32**，
> 4 条安全关键变异 + M0/M1 双对照全部按硬规矩 #65 取证并三重还原。
> **顶回控制者 2 处**（都是 Critical 级：简报给的 `apply_safety` / `apply_overrides` 签名
> 拿不到 P5-A3 与 P5-A8 要求的数据），**没按派单做的地方 0 处**（两处顶回都在报告里显式写明，
> 没有静默偏离）。**待清扫 6 条**。
> **本轮 fix round 数：0**（还没进过评审）。

---

## 1. 环境与基线复现

### 1.1 开工第一件事（硬规矩 #73 的冒烟）

命令与实跑输出（在 `backend/` 下）::

    python -c "import sqlalchemy, pandas, numpy, yaml, sys; print(sys.version); print(sqlalchemy.__version__, pandas.__version__, numpy.__version__, yaml.__version__)"

::

    3.11.1 (tags/v3.11.1:a7a450f, Dec  6 2022, 19:58:39) [MSC v.1934 64 bit (AMD64)]
    2.1.3 3.0.6 2.4.6 6.0.3

即 **Python 3.11.1 / SQLAlchemy 2.1.3 / pandas 3.0.6 / numpy 2.4.6 / PyYAML 6.0.3**，
与派单第 1 节逐字一致。无 venv（解释器在 `C:\Python`）。

⚠️ **没有撞上 `ImportError: DLL load failed`**：整个 Task 期间（约 20 次 pytest 调用、
6 次变异取证子进程）**一次都没有**出现 Windows Smart App Control 拦 `.pyd` 的形态
（账本 Ruling 121/122）。故无需按派单第 1 节的要求停手交回。

### 1.2 仓库状态复核

| 项 | 派单说的 | 实测 | 相符 |
|---|---|---|---|
| 分支 | `feature/plan-02-prescription-engine` | 同 | ✓ |
| HEAD | `c8e26b8` | `c8e26b8` | ✓ |
| 工作树 | 干净 | 只有控制者自己的 2 个未跟踪文件（`.superpowers/…/_mk_brief5.py` 与 `task-5-brief.md`） | ✓（`backend/` 下干净） |
| 全量 | 592 passed | **592 passed in 61.43s** | ✓ |
| 覆盖率 | 541 / 0 / 132 / 0 / 100% | 未复跑（见 1.3 的说明） | — |
| 扫描面 | 28（pipeline 7 + db 11 + domain 10） | **`[('db', 11), ('domain', 10), ('pipeline', 7)] 28`** | ✓ |
| 公开面 | `__all__` = 24 | `len(_PRESCRIPTION_PUBLIC_BASELINE) == 24` 与 `len(__all__) == 24` 双双坐实（P5-A13 的处置：先读那条字面断言，不再用探针去数） | ✓ |

扫描面的复核命令（在**仓库根**跑，与 `tests/architecture/test_layering.py` docstring 里那一条逐字相同）::

    python -c "import pathlib,collections; c=collections.Counter(p.parts[2] for p in pathlib.Path('backend/app').rglob('*.py') if p.parts[2] in ('pipeline','db','domain')); print(sorted(c.items()), sum(c.values()))"

### 1.3 覆盖率基线为什么没在开工前复跑

派单只要求跑 `pytest -q` 冒烟。开工前复跑一次带 `--cov` 的全量要 **135 s**（实测结案时那次是
134.65 s），而基线值 `541 / 0 / 132 / 0 / 100%` 已在派单与简报里逐字给出、且结案时的实测
（**888 / 0 / 260 / 0 / 100%**）能与它**逐项对账**：

    541 + 27(intensity) + 124(assembler) + 96(safety) + 96(override) + 4(prescription/__init__) = 888  ✓
    132 +  12           +  38            + 40         + 38           + 0                          = 260  ✓

两个加和都精确成立，故基线值被**独立复核**过（不是照抄），省下了一次 135 s 的空跑。
`prescription/__init__.py` 那 4 个 stmts 是 5.5 新增的 4 句 `from .x import (…)`。

### 1.4 禁区复核（结案时亲跑）

| 禁区 | 要求 | 实测 |
|---|---|---|
| `backend/pe.db` | 不得存在 | **不存在** ✓ |
| `backend/data/seed/` | 0 文件 | **0** ✓ |
| `backend/data/national_standard_2014.csv` | sha256[:16] == `D2C8E539E2FA0029` | **`D2C8E539E2FA0029`** ✓ |
| `backend/data/exercises.yaml` | 指纹 `3DE598AF38631209` | **`3DE598AF38631209`** ✓ |
| `backend/data/exercise_equivalence.yaml` | 指纹 `822CB86A5E998301` | **`822CB86A5E998301`** ✓ |

**`backend/data/` 一个字节都没动**（18 套模板 YAML 同样未改：本 Task 要坏形状的模板一律用
`dataclasses.replace` 造副本）。也没跑过 `app.seed.generate` / `app.pipeline.backfill` /
`app.pipeline.daily`。`git status --porcelain` 在 5.5 commit 之后只剩控制者那 2 个未跟踪文件。

---

## 2. 逐节交付

| 节 | commit | 新建/改动 | 新增测试 | 该节末全量 | 该节 domain 覆盖率（新模块） |
|---|---|---|---|---|---|
| 5.1 | **`d78120a`** | `app/domain/prescription/intensity.py`、`tests/domain/test_prescription_intensity.py` | **10** | **602 passed** in 59.78 s | `intensity.py` **27 / 0 / 12 / 0 / 100%** |
| 5.2 | **`1c5b9bb`** | `assembler.py`、`test_prescription_assembler.py` | **26** | **628 passed** in 59.67 s | + `assembler.py` **124 / 0 / 38 / 0 / 100%** |
| 5.3 | **`5f05dda`** | `safety.py`、`test_prescription_safety.py` | **25** | **653 passed** in 61.60 s | + `safety.py` **96 / 0 / 40 / 0 / 100%** |
| 5.4 | **`14673aa`** | `override.py`、`test_prescription_override.py` | **19** | **672 passed** in 65.56 s | + `override.py` **96 / 0 / 38 / 0 / 100%** |
| 5.5 | **`fc8f5a8`** | `prescription/__init__.py`、`tests/test_refdata_prescription.py`（改） | **0** | **672 passed** in 66.96 s | **TOTAL 888 / 0 / 260 / 0 / 100%** |

新增测试合计 **80** 条（10 + 26 + 25 + 19），`592 + 80 = 672` ✓（passed 数自己数的，
硬规矩 #44：没有照抄派单——派单也没给这个数）。

覆盖率四格（结案时亲跑，`cd backend; python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing`）::

    Name                                   Stmts   Miss Branch BrPart  Cover
    app\domain\prescription\__init__.py        9      0      0      0   100%
    app\domain\prescription\assembler.py     124      0     38      0   100%
    app\domain\prescription\exercises.py      38      0      6      0   100%
    app\domain\prescription\intensity.py      27      0     12      0   100%
    app\domain\prescription\match.py          41      0     12      0   100%
    app\domain\prescription\override.py       96      0     38      0   100%
    app\domain\prescription\safety.py         96      0     40      0   100%
    app\domain\prescription\templates.py      58      0      0      0   100%
    （另 6 个 Plan 01 的 domain 模块全部仍 100%）
    TOTAL                                    888      0    260      0   100%

    671 passed, 1 skipped in 134.65s

⚠️ **那个 1 skipped 不是本轮引入的**：带 `--cov` 时是 `671 passed + 1 skipped`、不带时是
`672 passed`。跳过的唯一一条是 `tests/pipeline/test_backfill.py` 里既有的**墙钟断言**，它自己
写着 `if sys.gettrace() is not None: pytest.skip(...)`（理由逐字是「带 --cov=app.domain 时
同一台机器的实测区间是 54.7–70.8 s，余量 < 2×，按硬规矩 #42 属 flaky 断言，故跳过」）。
那个文件的 docstring 里还记着「Task 2 实测 `529 passed, 1 skipped`」，即**这个 skip 从 Task 2
就在**。不带 `--cov` 的那一列（`672 passed`）才是本节报的数。

### 2.1 TDD 的红档取证（每节都先看到红）

四节都先写测试文件、再实现，且**红的原因逐节确认过**是「模块不存在」而不是别的意外：

| 节 | 红档实测输出（`pytest -q` 的末行） |
|---|---|
| 5.1 | `ModuleNotFoundError: No module named 'app.domain.prescription.intensity'` → `1 error in 0.35s` |
| 5.2 | `ModuleNotFoundError: No module named 'app.domain.prescription.assembler'` → `1 error in 0.53s` |
| 5.3 | `ModuleNotFoundError: No module named 'app.domain.prescription.safety'` → `1 error in 0.60s` |
| 5.4 | `ModuleNotFoundError: No module named 'app.domain.prescription.override'` → `1 error in 0.64s` |

⚠️ 5.3 与 5.4 的红档是**事后补取证**的：这两节我在写完测试文件之后接着就写了实现，
于是用 `Move-Item` 把实现文件挪到 `$env:TEMP`、跑一遍拿到 `ModuleNotFoundError`、再挪回来。
文件字节没变（挪回来之后 sha256 与 M0 那一份逐字一致，见第 3 节）。5.1 与 5.2 是**当场**红的。

⚠️ **实现期撞到 3 次「测试自己写错」**，全部是期望值算错、不是生产码错，逐条列出
（这正是硬规矩 #44 要「期望值自己算」的价值——照抄派单就不会发现自己算错了）：

1. `test_rest_min_is_not_counted_as_volume` 原来断言四周的 `weekly_volume` **都**等于 `48.0`，
   实测第 2 周是 `50.4`（`48.0 × 1.05`）——忘了 `week_deltas`。改成逐周字面
   `[48.0, 50.4, 52.8, 40.8]`。
2. `test_bmi_missing_is_recorded_as_skipped_not_as_clean` 原来给的是
   `muscle_mass_kg=40.0, muscle_p10=30.0`（**40 > 30，压根不触发**）却断言触发了。
   改成 `24.0 / 25.0`。
3. `test_appended_addons_go_to_the_end_of_every_session_in_trigger_order`（原名
   `test_the_appended_addon_goes_to_the_end_of_every_session_of_every_week`）原来断言
   `blocks[-1]` 是 `resistance_priority`，实测末尾是 `energy_expenditure_plus_10pct`
   ——两个触发同时命中时追加序 = `_TRIGGER_MAP` 的迭代序（`muscle_low_p10` 先于
   `body_fat_abnormal`）。改成断言完整的四元组，并把「追加序是承重的」写进 docstring。

### 2.2 派单第 6 节那张算例表的对拍结果

**逐格相符，两边没有一个数不一样。** 独立重算过程（本机 Python 3.11.1 亲跑 `repr`）：

| 量 | 我的重算 | 派单给的 | 相符 |
|---|---|---|---|
| `hrmax(20)` | `208 - 0.7 * 20` = `194.0` | `194.0` | ✓ |
| `hr_zone(194.0, 60, 70)` | `int(194.0*60/100.0)` = `int(116.4)` = `116`；`int(-(-135.8 // 1))` = `136` → `(116, 136)` | `(116, 136)` | ✓ |
| `interval_run` 的 base | `work_min 3 × sets 4` = `12` min/课 | `12` | ✓ |
| `interval_run` 的 weekly | `12 × 4` = `48.0` min/周 | `48.0` | ✓ |
| 第 1 周 | `repr(48.0*0.8*1.0)` = `38.400000000000006` → `round(…,1)` = **`38.4`** | `38.4` | ✓ |
| 第 4 周 | `repr(48.0*0.8*0.85)` = `32.64` → **`32.6`** | `32.6` | ✓ |
| `compound_circuit` 的 base | `rounds 3 × reps 10` = `30` reps/课 | `30` | ✓ |
| weekly / 第 1 周 / 第 4 周 | `120.0` / `96.0` / `repr(120.0*0.8*0.85)` = `81.6` → **`81.6`** | `120.0` / `96.0` / `81.6` | ✓ |
| 系数 | 档 `<60` → `0.8`，男 → `1.0`，`round(0.8*1.0, 2)` = `0.8` | `0.8` | ✓ |

⚠️ **两处派单没写、而实现必须定的中间值**（都由亲跑 `repr` 定，已字面写进测试）：
第 2 周 `40.32000000000001 → 40.3`、第 3 周 `42.24000000000001 → 42.2`；
`compound_circuit` 第 2/3 周 `100.80000000000001 → 100.8`、`105.60000000000001 → 105.6`。
`weekly_volume_base`（`RED-END-ABN-01`）= `4 课 × (12 + 30)` = **`168.0`**，派单没给这个数。

⚠️ **算式写法承重**（派单未提，实测发现）：`194.0 * 60 / 100.0` = `116.4`，而
`194.0 * 0.6` = **`116.39999999999999`**；`194.0 * 70 / 100.0` = `135.8`，而 `194.0 * 0.7` =
**`135.79999999999998`**。两者取整后同为 `(116, 136)`，故断言对这个选择不敏感；生产码仍写
`/ 100.0` 那一种（离「百分比」的语义更近，且不给将来某个 `round` 埋 1e-14 的坑）。
这层因果写在 `intensity.hr_zone` 的 docstring 里。

### 2.3 逐节的关键落地口径（只记「与派单不同或派单没给」的部分）

**5.1 `intensity.py`**

* **不 import `datetime`**（P5-A4 的同一条纪律）：`ALLOWED_MODULES` 实测 =
  `{dataclasses, enum, collections, collections.abc, numpy, typing}`，`datetime` 与 `math`
  都不在其中。`templates.py` 的既有处置是**改类型**（`reviewed_at: str | None`），
  但 `age_from` 的日期**要参与算术**（折成 ISO 串再解析回来更绕），故本模块选了另一条路：
  **duck typing + 前向引用字符串标注**（`birth: "dt.date"`），运行时只读
  `year` / `month` / `day`。**代价已写进模块 docstring**：`dt` 在命名空间里不存在，故
  `typing.get_type_hints(age_from)` 会抛 `NameError`；今天全仓没有任何一处调它
  （`inspect.signature` 不求值标注，先例是 `tests/domain/test_derive.py` 的
  `test_smi_is_not_an_input_at_all`）。守卫是 `test_age_from_accepts_any_object_with_year_month_day`
  ——它钉住 duck typing 契约本身，免得下一个人以为可以在这里补 `import datetime`。
  `assembler.py`（`StudentProfile.birth` / `assemble(as_of=…)`）与 `override.py`
  （`OverrideRecord.applied_at`）沿用同一处置。
* **`age` 的校验对 `measured` 那一档同样生效**，校验顺序是**先年龄、后实测值**。派单那句
  「校验 `60 <= measured <= 220` 后**直接返回**」读起来像是跳过年龄校验，但那会让
  `hrmax(age=-5, measured=180)` 返回 180——一个荒谬的年龄说明 `StudentProfile` 本身坏了
  （`birth` 缺失或 `as_of` 传错），「心率是实测的所以年龄无所谓」是一个错误的安慰。
  派单把年龄校验写成**独立的一句**（不在 `else` 分支里），故本实现与派单文本一致。
* `hrmax(99)` 的字面值 **`138.7`**（`repr(208 - 0.7*99)`，精确无尾数）；派单给的三个
  （`194.0` / `195.4` / `190.5`）也都精确，故一律用 `==` 而不是 `pytest.approx`。

**5.2 `assembler.py`**

* **`structure` 的值域比派单描述的更规整**（亲扫 130 个 block）：时长类 **78** 个全是
  `{sets: 4, work_min: 3, rest_min: 2}`、次数类 **52** 个全是 `{rounds: 3, reps: 10}`，
  **各只有一种取值**。故「两种键集」这个判据在真仓上没有歧义；`_base_volume` 用
  `frozenset(keys) == …` **相等**判定（不是「包含这几个键」），混形状 `{sets, work_min,
  rest_min, rounds}` 会响。
* **`sessions_per_week` 的分布有两种口径，派单只给了一种**：亲扫按 `exercise_ref` **去重**是
  `{2: 12, 3: 14, 4: 16}`（共 42 个 ref / 18 套模板），**块数加权**是
  `{2: 24, 3: 42, 4: 64}`（共 130 个 block）。两者自洽（`12×2 = 24`、`14×3 = 42`、
  `16×4 = 64`）。派单 P5-A2 给的是**块数加权**那一份，测试
  `test_every_block_appears_in_every_session_of_the_real_templates` 断言的也是它。
  两种口径都确认了「每个 ref 的 `sessions_per_week` 恒等于该模板的 `weekly_frequency`」
  （探针里那一句 `assert` 对 42 个 ref 全部通过）。
* **`endurance_score is None` 时连性别修正也不做**，返回字面 `1.0`（不是 `round(1.0*0.9, 2)`）。
  派单只写「用 `1.0`」，本实现按字面办，理由写进 `_volume_factor` 的 docstring：
  `1.0` 是「不知道就不动」的中性值，而 `0.9` 是一个**基于档位表**的修正，档位未知时它没有依据。
* **`assembly_snapshot["as_of"]` 存 `isoformat()` 之后的字符串、`week_deltas` 存 `list`**
  （派单没写这两个的类型）：`datetime.date` 与 `tuple` 都**不是 JSON 可序列化的**，而这个快照
  要落进 `prescription.assembly_snapshot` 那个 JSON 列（Task 6）。同理
  `safety_triggers` / `safety_skipped` 也是 `list`。
* **`formula` 恒为 `"tanaka"`，即使用了实测 HRmax**（派单说「简化后恒为 tanaka」）。
  为了让它不变成一句谎，`assembler.py` 的 docstring 里写明：`formula` 记的是「**本构建实现
  哪个公式**」，而「这次用的是不是公式值」由快照的 `hrmax` 那一格承担。守卫
  `test_hrmax_prefers_the_measured_value` 同时断言 `hrmax == 186.0` 与 `formula == "tanaka"`。
* **`intensity` 四档各有显式的一支 + 词表外抛 `ValueError`**（派单只点了四档的文案，没点
  「词表外怎么办」）。加这一支的理由与 `exercise_ref` 的第二道校验同构，且**它是分支覆盖
  100% 的必要条件**（`if/elif` 链的最后一支必须有测试）。守卫是
  `test_an_unknown_intensity_type_is_rejected`（手工构造 `Intensity(type="watt_bike")`）。
  `none` 那一档的文案逐字照派单：`"模板未指定强度（spec §7.2 只给了红层数值，见 spec §14）"`。

**5.3 `safety.py`**

* ⚠️ **签名加了两个 keyword-only 形参**（顶回，见第 5 节关切 1）。
* **`Substitution` 是逐 block 实例的、`warnings` 按 ref 去重**（派单没定这两个的粒度）。
  `interval_run` 在 `RED-END-ABN-01` 里出现 4 周 × 4 课 = **16** 次，故 16 条
  `Substitution`（它带 `week` 与 `day`，是**审计**数据，教师要能逐课对账）；而
  「找不到替身」的 warning **每个 ref 只一条**（16 条同样的 warning 会把复核队列刷成噪音，
  而队列一旦被淹没，真正需要人看的那一档就没人看了）。守卫是
  `test_a_partially_solvable_table_substitutes_what_it_can_and_flags_the_rest`
  （`assert len([w for w in outcome.warnings if "sprint_50m_intervals" in w]) == 1`）。
* **`Substitution.trigger` 记第一个命中的走等价表的触发**（两个都命中时只记 `bmi_over_30`）：
  替换这件事**只发生了一次**（替身是 `low` 冲击，第二个触发再走一遍时它已经不是 `HIGH`），
  记两条会让教师以为换了两次。
* **跑量下调无条件乘**（`× 1.0` 是恒等，`round` 一个已 round 的值仍是它自己），于是
  「没有触发」那一档不需要一条 `if`——少一个分支就少一个可能写错的地方。
  守卫 `test_no_trigger_at_all_is_a_noop_that_still_appends_the_three_keys` 断言
  `outcome.package.weeks == _pkg().weeks`（逐字段相等）。
* **替身继承原动作的剂量**（`intensity_text` / `hr_zone` / `structure` / `volume_unit` /
  `sessions_per_week` 全部原样，只有 `weekly_volume` 跟着下调系数变）。派单没写这一条，
  但 `exercise_equivalence.yaml` 的注释逐字给了依据：「固定自行车把体重从关节上卸掉，
  同时**保留 60–70% HRmax 的间歇刺激**」。守卫 `test_the_substitute_inherits_the_original_dose`。
* **等价替换的冲击上限取 `ImpactLevel.LOW`**（`eq.lookup(ref, ImpactLevel.LOW)`）：
  spec §7.4 说的是「换**低冲击**等价动作」，而真表 10 条映射的 `max_impact` 全是 `low`。
  `EquivalenceTable.lookup` 按 `IMPACT_RANK[max_impact] >= IMPACT_RANK[ceiling]` 过滤，
  故 ceiling = LOW 只认 low 替身。
* **`safety_skipped` 的三个 token 字面固定**：`bmi_missing` / `muscle_mass_missing` /
  `muscle_p10_missing`（后两个**各自**留痕，缺一个就少一条判据）。
  ⚠️ **没有 `body_fat_missing`**：`SafetyInput.body_fat_abnormal` 是 `bool`，来源是 Plan 01 的
  `BodyCompFlag.abnormal`，而 **`False` 已经包含「数据缺失所以无从判定」这一整类**
  （Plan01 Ruling 97③）。「为什么是 `False`」是 `derive.body_comp_flag` 的账、不是安全层的账。
  这个「不对称」写进了 `SafetyInput` 的 docstring。
* **`safety_volume_factor` 不 round**（保持乘积原值 `0.7200000000000001`），只有被它乘出来的
  `weekly_volume` 才 `round(…, 1)`。派单说「系数用 `pytest.approx`」，本实现照办，并且
  **额外断言 `!= 0.72` 与 `== 0.7200000000000001`**，把 P5-A6 那个事实钉住——
  免得下一个人「顺手修掉」这个看起来像 bug 的尾数（round 掉它会掩盖「系数是乘出来的」）。

**5.4 `override.py`**

* ⚠️ **签名加了一个 keyword-only 形参 `exercises`**（顶回，见第 5 节关切 2）。
  **不做成可选缺省 `None`**：那会让「传了 `SUBSTITUTE_EXERCISE` 却忘了传 `exercises`」
  变成一个只在**那一条记录**上才炸的 `TypeError`，离真因隔一层。
* **五种 kind 的语义派单基本没给**（只给了名字与「`old_value` / `new_value` 是 `str`」），
  逐种落地口径与理由都写在 `override.py` 模块 docstring 的那张表里，这里只记三个决定：
  1. **`WEEKLY_FREQUENCY` 必须重算量**：`weekly_volume` 是**周量**，砍掉一课而不改它，
     那个数就在撒谎（教师端显示 48 min/周而学生实际只做 36 min）。故
     `weekly_volume × N/原课次` 且 `sessions_per_week = N`。重算是**相对当前课次**的，
     故 `4 → 3 → 2` 与 `4 → 2` 得到同一个量（`24.0`）——复合不漂移。
     `N > 该周课数` 与 `N < 1` 都拒绝、不夹取（算法**造不出**第 5 课；`0` 课与 `PAUSE`
     是两件事）。
  2. **`INTENSITY_STEP` 的 `new_value` 是「目标心率区间的百分比点数增量」**，
     `delta = int(step × hrmax / 100)`，`hrmax` 读 `assembly_snapshot["hrmax"]`
     （**不重新算**：快照里那个数才是这张处方当初用的值——可能是实测值而不是 Tanaka，
     重算一次就是同一条规则的第二个住址）。区间**整体平移**（宽度不变），故不需要重新做
     保守取整。`int()` 是向零截断：`step = -5`、`hrmax = 194.0` → `int(-9.7)` = **-9** →
     `(116, 136)` 变 **`(107, 127)`**。低界 `<= 0` 拒绝、不夹取。
  3. **`VOLUME_SCALE` 允许 `> 1`（加量）**：`volume_reduction` 那两个系数被加载器限制在
     `(0.0, 1.0)`（`> 1` 是「安全触发反而加量」），而**教师覆盖不是安全触发**——
     一个恢复得快的学生可以被教师加量。只拒绝 `<= 0`。
* **`_rebuild` 在命中 0 个 block 时抛 `ValueError`**（派单没要求）：一个打错的 `target`
  （`"interval_runn"`）会让覆盖**静默无事发生**，而教师以为自己已经改过了——那正是
  「静默跳过」在覆盖侧的形状。`SUBSTITUTE_EXERCISE` / `INTENSITY_STEP` / `VOLUME_SCALE`
  三种共用这一个 helper，故只有**一个**分支要覆盖。守卫在
  `test_substitute_exercise_rejects_an_unknown_ref_on_either_side` 与
  `test_volume_scale_rejects_a_non_positive_factor_and_an_unknown_target`。
* **分派用 `is` 而不是 `==`**：`OverrideKind.PAUSE == "pause"` 为真而
  `OverrideKind.PAUSE is "pause"` 为假，故一个裸字符串 `kind`（例如从 JSON 列读回来、
  忘了过 `OverrideKind(...)`）会落到 `ValueError` 那一支**当场响**，而不是被静默当成
  某一种覆盖执行。守卫 `test_an_unknown_override_kind_is_rejected`。
* **空列表也产出新包**（`replace(pkg)`）：`out is not pkg` 是「纯函数不返回入参」这条纪律的
  一部分，否则调用方拿到同一个对象、以为它是覆盖后的产物。守卫 `test_no_records_is_a_noop`。
* **`target` 的「周次」那一档今天没有 kind 用它**（派单说 `target` 是「周次或 `exercise_ref`」）：
  spec §7.5 的五种覆盖里没有「只改第 3 周」这一种，而按周微调是 `week_deltas` 的活
  （Task 8 的读模型）。这句话写进了 `OverrideRecord` 的 docstring。

**5.5 收尾**

* ⚠️ **派单只点了 2 处要改，实际是 3 处**：`__init__.py` 的 `__all__`、
  `_PRESCRIPTION_PUBLIC_BASELINE`、以及那句 `assert len(...) == 24`（派单点了这一句）——
  但还有**第四处**派单没点：`_OWNED_MODULES`（支 5 的「穷尽」判据只对这个清单里的模块成立）。
  不把四个新模块加进去，它们的公有顶层定义就**没人管**（往 `safety.py` 加一个新常量却忘了
  重导出会完全静默，而那正是支 5 唯一守得住的方向）。已从 3 个扩到 **7** 个。
  同一处还有两句 `assert len(...) == 24`（支 1 的长度与无重名），都改成了 `43`。
* **5.1–5.4 那四个 commit 里 `__init__.py` 一个字都没改**，四个新模块的测试直接从**所有者
  模块** import（口径照 `templates.py` 模块 docstring 那句「**新代码请直接从所有者导入**」）。
  理由：否则每建一个模块就要改一次这份字面基线（`24 → 27 → 35 → 39 → 43`，四次），
  而每一次改动都是一次「抄漏一个名字」的机会（P5-A13 记的控制者错误 #139 同型）。
  派单第 2 节把「修改 2 个文件」列为交付物、第 9 节要求「分 5 次 commit」，两者在本实现里
  是这样相容的：那 2 个文件的改动**全部落在第 5 个 commit**。

---

## 3. 变异取证（4 条安全关键 + M0 + M1）

**取证脚本** `$env:TEMP\t5_mutate.py`（**未入库**：它是本 Task 的一次性工具，
口径照 commit `3473dc6`「清掉误入库的三个 Task 4 预检一次性脚本」）。
每条变异的流程是：**记 sha256 → 按字符串替换打变异（先 `assert text.count(old) == 1`）→
跑 pytest 记开火的断言 → 按字节写回原文 → 复核 sha256 与变异前一致 → 重跑确认绿**
（即硬规矩 #65 的三重还原）。

### 3.0 M0：不变异时全绿

跑的是「四个新测试文件 + 两份架构守卫 + 公开面基线」::

    python -m pytest -q tests/domain/test_prescription_{intensity,assembler,safety,override}.py
                        tests/architecture tests/test_refdata_prescription.py

→ **142 passed in 1.93 s，退出码 0**（10 + 26 + 25 + 19 + 6 + 56）。四个生产模块的 sha256
（**这是后面五次还原的对账基准**）::

    intensity.py  9d8336d25a2df1967a02eb5629b2ec2252cff637b18ea9fd46d5264947c78e61
    assembler.py  d5e7890e13bf0d877b7bd3500f01a0cc343532b2f55e62cd468ed3d8d18894cc
    safety.py     bc471a4b5161d10c7006d69fa67ecd44eac5cda6722c7a304a84456900a8e108
    override.py   1e2e088c886b499034bf77f9abd442c7bfb36cf9a81832837d900ca98163b337

### 3.1 变异 ① `bmi > 30` → `>= 30`

| 项 | 值 |
|---|---|
| 改了哪一行 | `safety.py` 的 `elif inp.bmi > _BMI_LIMIT:` → `elif inp.bmi >= _BMI_LIMIT:` |
| 变异后 sha256 | `494f2cd26121886143b7022b904c62c4c43918830ac5b7fb668f96f7aa3b2781` |
| 哪条测试红 | `tests/domain/test_prescription_safety.py::test_bmi_exactly_30_does_not_trigger` |
| **哪个断言分支开火** | 该测试的**第一句**：`assert boundary.package.assembly_snapshot["safety_triggers"] == []` → `AssertionError: assert ['bmi_over_30'] == []`（`test_prescription_safety.py:281`） |
| 结果 | `1 failed, 24 passed`，退出码 1 |
| 还原后 sha256 | `bc471a4b…a8e108`，**与变异前逐字一致** |
| 还原后重跑 | `25 passed`，退出码 0 |

⚠️ 同一条测试里的**第二个断言**（`just_over` 那一半，`bmi = 30.1` 必须触发）**保持绿**：
变异只把边界那一格从「不触发」翻成「触发」，`30.1` 在两种比较符下都触发。故这条测试的
**两半必须都在**——只有 `30.0` 那一半的话，「`>` 改成 `<`」这类反向变异就抓不住。

### 3.2 变异 ② 删掉「找不到等价动作 → `needs_review`」

| 项 | 值 |
|---|---|
| 改了哪一行 | `safety.py` 里 `if substitute is None:` 分支下的 `needs_review = True` **整行删除** |
| 变异后 sha256 | `87ac016534942ca0829fd09cbc4350664bdacf2d1f73262a2281932f10e93cc6` |
| 哪两条测试红 | `test_missing_equivalent_sets_needs_review_and_keeps_the_block`（**Review Focus 第 5 条的那一条**）与 `test_a_partially_solvable_table_substitutes_what_it_can_and_flags_the_rest` |
| **哪个断言分支开火** | 两条都是同一句：`assert outcome.needs_review is True` → `assert False is True`（`test_prescription_safety.py:574` 与 `:600`） |
| 结果 | `2 failed, 23 passed`，退出码 1 |
| 还原后 sha256 | `bc471a4b…a8e108`，**与变异前逐字一致** |
| 还原后重跑 | `25 passed`，退出码 0 |

⚠️ **两条红的其余断言全部保持绿**（该 block 原样保留、warning 点名 ref/触发/版本号、
`substitutions == ()`），即「删掉 `needs_review`」这一个改动**只**被那一句抓着。
这正是 Review Focus 第 5 条要求的「必须有测试钉住**它没有被静默跳过**」的落点：
删掉这一行之后处方仍然看起来完全正常（block 在、warning 在），只有 `needs_review`
从 `True` 变成 `False`，于是 Task 6 会把它当成一张**不需要人工复核**的处方落库。

### 3.3 变异 ③ 删掉 `age <= 0` 的守卫

| 项 | 值 |
|---|---|
| 改了哪一行 | `intensity.py` 的 `if age <= _AGE_MIN_EXCLUSIVE or age >= _AGE_MAX_EXCLUSIVE:` → `if age <= -1e9 or age >= _AGE_MAX_EXCLUSIVE:`（把下界挪到不可能取到的值，等价于删掉它，而**不动上界**） |
| 变异后 sha256 | `bcbfc1fdb4331a84ab00300a073688237a33bd4dc50ed8a80fa255199f12a072` |
| 哪条测试红 | `test_hrmax_rejects_a_non_positive_age_and_prints_the_age_it_got` |
| **哪个断言分支开火** | `with pytest.raises(ValueError): hrmax(bad_age)` → `Failed: DID NOT RAISE ValueError`（第一格 `bad_age = 0`，此时 `hrmax(0)` 返回 `208.0`） |
| 结果 | `1 failed, 9 passed`，退出码 1 |
| 还原后 sha256 | `9d8336d2…c78e61`，**与变异前逐字一致** |
| 还原后重跑 | `10 passed`，退出码 0 |

⚠️ **上边界那一条 `test_hrmax_rejects_an_age_of_100_or_more_and_prints_the_age_it_got`
保持绿**（它打的是 `or` 的**右半**，变异没动它）。这一格值得记：**「删掉 `age <= 0` 的守卫」
只让一条测试红**，而那条测试之所以能红，是因为它挑的年龄是 `0` 与 `-5` 这种**可辨识**的值
（一条只断言 `"0" in message` 的测试会被任何含 0 的消息蒙混过去）。

### 3.4 变异 ④ 把 `hr_zone` 的取整方向反过来

| 项 | 值 |
|---|---|
| 改了哪一行 | `intensity.py` 的 `return int(low_bpm), int(-(-high_bpm // 1))` → `return int(-(-low_bpm // 1)), int(high_bpm)`（低界改向上、高界改向下） |
| 变异后 sha256 | `a311d0c422d6a69b14139bd6a884b02e7c044c263da7dae707f862665a48cc9d` |
| 哪条测试红 | `test_hr_zone_rounds_conservatively_outward` |
| **哪个断言分支开火** | 该测试的**第一句**：`assert hr_zone(194.0, 60, 70) == (116, 136)` → `AssertionError: assert (117, 135) == (116, 136)`（`test_prescription_intensity.py:130`） |
| 结果 | `1 failed, 9 passed`，退出码 1 |
| 还原后 sha256 | `9d8336d2…c78e61`，**与变异前逐字一致** |
| 还原后重跑 | `10 passed`，退出码 0 |

**区间从 `(116, 136)` 宽 20 bpm 变成 `(117, 135)` 宽 18 bpm**——**窄了 2 bpm**，正是
「低界向下、高界向上（区间略宽比略窄安全）」那个决定要挡的方向。
⚠️ 这一条能红的**前提**是那两个端点都不是整数（`116.4` 与 `135.8`）：派单给的算例
`hr_zone(194.0, 60, 70)` 恰好满足，故本文件把它作为「暴露取整方向」的那一格，
另外两格（`(194.0, 50, 50) == (97, 97)`、`(200.0, 0, 100) == (0, 200)`）是**绿档**
（硬规矩 #50：端点本来就是整数时不许额外放宽一格）。

### 3.5 M1：语义等价改写后**仍全绿**（证明尺子不恒红）

| 项 | 值 |
|---|---|
| 改了什么 | `intensity.py` 的 `age_from` 函数体：`age = as_of.year - birth.year` / `if (as_of.month, as_of.day) < (birth.month, birth.day): age -= 1` / `return age` 三行 → `return as_of.year - birth.year - ((as_of.month, as_of.day) < (birth.month, birth.day))` 一句（`bool` 参与算术，语义逐格相同） |
| 变异后 sha256 | `eb9e78e77c06514a450fd5b5541e5d9ac2eb61ff543686e9009e54123ed7e29e` |
| 结果 | **四个新测试文件 80 passed，退出码 0**（`intensity` 10 + `assembler` 26 + `safety` 25 + `override` 19） |
| 还原后 sha256 | `9d8336d2…c78e61`，**与变异前逐字一致** |
| 还原后重跑 | `80 passed`，退出码 0 |

**它证明了什么**：那 80 条断言钉的是 `age_from` 的**行为**（周岁、生日当天不减、
生日前一天减一、duck typing），不是它的**写法**。同时它也顺带证明了「分支覆盖 100%」
不会把一种合法重写挡在门外：改写之后 `if` 那一支消失、branch 数从 12 降到 10，
覆盖率仍是 100%（没有新增未覆盖分支）。

### 3.6 ⚠️ 取证过程中撞到的一个新失效形态（建议进账本）

**第一轮跑变异 ④ 时，「还原后重跑」得到了一次假红**：`sha256` 已经逐字还原成功
（打印 `sha256 与变异前一致: True`），而 pytest 仍然报 `assert (117, 135) == (116, 136)`，
退出码 1——看起来像「三重还原失败了」，而源码其实是对的。

**机制**：CPython 的 `.pyc` 失效判据是 **(源文件 `st_mtime` 截断到秒, 源文件 `size`)**。
变异 ④ 的新旧两行**恰好等长**（都是 **47** 字符：
`    return int(low_bpm), int(-(-high_bpm // 1))` 与
`    return int(-(-low_bpm // 1)), int(high_bpm)`），于是文件 `size` 一个字都没变；
而「变异 → 跑 → 还原 → 重跑」四步在**同一秒内**完成，于是 `mtime` 截断到秒之后也没变。
两个判据同时没变 → `.pyc` 被判有效 → **Python 加载的是变异版的字节码**。

**为什么只有变异 ④ 撞上**：① ② ③ 与 M1 的新旧文本长度都不同（② 是整行删除、
③ 与 M1 都改变了行长度），`size` 一变 `.pyc` 立刻失效。

**修法**（已落进取证脚本）：每次跑 pytest 之前 `shutil.rmtree` 掉 `backend/app/` 下所有
`__pycache__`，并给子进程设 `PYTHONDONTWRITEBYTECODE=1`。修完之后 4 条变异 + M0 + M1
**六次**全部重跑：六次的「还原后 sha256」都与变异前逐字一致、六次的「还原后重跑」
退出码都是 0。

**建议**：这一条与账本里已有的「落盘唯一权威是 shell」（硬规矩 #46）同族——都是
「你以为你看的是磁盘，其实你看的是缓存」。建议立一条硬规矩：
**变异取证（或任何「改文件 → 跑 → 还原 → 再跑」的对照实验）必须先清 `__pycache__`
并禁写字节码，否则一次等长变异 + 同秒还原就会给出假红（或更坏：假绿）**。
更坏的那一半是：如果变异是**等长且语义等价**的，这个机制会让「变异后仍全绿」看起来
像是尺子没牙，而其实是字节码根本没换。

---

## 4. 待清扫清单（Ruling 145：散文与实测的偏差，不单独返工）

**6 条**，全部是散文精度问题，**没有一条会让生产码错、守卫假绿或数据不可追溯**
（那三类都当场修了，见第 5 节）。

1. **P5-A2 的分布是「块数加权」那一份，简报没说清口径**。简报写「130 个 block 的
   『一周内出现次数』实测 = `{2: 24, 3: 42, 4: 64}`」，实测**按 `exercise_ref` 去重**是
   `{2: 12, 3: 14, 4: 16}`（共 42 个 ref），**块数加权**才是 `{2: 24, 3: 42, 4: 64}`
   （共 130 个 block）。两者自洽（`12×2`、`14×3`、`16×4`）。建议清扫时补一句
   「块数加权」，免得下一个人按 ref 去重数出 42 个以为数据变了。
2. **P5-A10 的两点「更正」本身都不成立**。P5-A10 说计划 5.3 写的「`derive.py:68-69`」
   **行号口径错**、且「明写严格大于」的**引文控制者未核**。实测两点都是对的：
   `app/domain/derive.py` 第 **68** 行逐字是
   「`# 体成分异常 C 的体脂率阈值（spec §6.3②）：男 > 20%、女 > 28%，**严格大于**。`」、
   第 **69** 行是 `BODY_FAT_LIMIT = {Sex.MALE: 20.0, Sex.FEMALE: 28.0}`，
   唯一消费点是第 **406** 行的 `body_fat_pct > limit`。故「`:68-69`」这个行号**恰好命中**
   那两行、「明写严格大于」这个引文**可以核**（注释里逐字有）。
   ⚠️ 我仍按硬规矩 #78 在 `safety.py` 的模块 docstring 里写成**可 grep 的原文片段**
   （`BODY_FAT_LIMIT = {Sex.MALE: 20.0, Sex.FEMALE: 28.0}` 与 `**P25 的比较符钉死为严格小于**`）
   而不是裸行号——那是 P5-A10 要求的**处置**，与「它的两点事实判断是否成立」是两件事。
3. **`rpe` 的值域两处口径不一致**。P5-A5 说「`rpe` 是 6–20」，而
   `templates.py` 里 `INTENSITY_TYPES` 的注释说「`rpe` 的出处是 spec §8.2 的课堂快评
   **RPE 0–10**」。本 Task 只渲染数字（`f"RPE {value:g}"`）、**不校验值域**，故两个口径
   今天都不承重；`assembler._render` 的 docstring 里两处都写了并标明「已记进待清扫」。
4. **简报 5.5 Step 5 只点了「`_PRESCRIPTION_PUBLIC_BASELINE` 24 → 新值」与那句
   `assert len(...) == 24`，漏了 `_OWNED_MODULES`**（3 → 7 个模块）与**第二句**
   `assert len(set(names)) == 24`。四处都已改（`__init__.py` 的 docstring 里那句
   「⚠️ 还有**第三处**」也已扩写）。建议清扫时把「公开面变更要同步的处数」从「三处」
   改成「四处」，并把 `_OWNED_MODULES` 列进去。
5. **简报 5.3 的 `Consumes` 段只列了「5.2 的 `TrainingPackage` / `AssembledBlock`、
   Task 2 的 `EquivalenceTable` / `ImpactLevel`」**，而落地还需要 Task 3 的 `Template`
   与 Task 2 的 `ExerciseSpec`（见第 5 节关切 1）。建议清扫时补齐。
6. **`test_prescription_templates.py:194` 那句「Task 2 实测 `529 passed, 1 skipped`」** 与
   本报告的 1 skipped 是同一件事的两个时点样本，不是矛盾；但简报 Task 5 全节里
   **没有一处**提到「带 `--cov` 时会有 1 个 skip」，而 5.5 Step 5 要求跑带 `--cov` 的验收命令、
   Step 5 又要求「全量 `pytest -q` 的 passed 数自己数」——两条命令给出的 passed 数**差 1**
   （671 + 1 skipped vs 672）。建议清扫时在计划里写明这两个数的口径差。

---

## 5. 关切

### 5.1 顶回控制者的地方（2 处，都是 Critical 级）

**⚠️ 共同点**：两处都是**简报的函数签名拿不到简报自己要求的数据**，与派单第 8 节说的
「控制者对着『当前目录形状』推理，实现者对着『守卫实际能抓到什么』推理」同型——
这里是「计划对着 `Produces` 列表推理，实现者对着**字段的值从哪来**推理」。

#### 关切 1（Critical）：`apply_safety(pkg, inp, eq)` 这个签名**实现不了 P5-A3**

* **哪条决定**：简报 5.3 的 `Produces` 段写 `apply_safety(pkg: TrainingPackage,
  inp: SafetyInput, eq: EquivalenceTable) -> SafetyOutcome`。
* **为什么错**：**同一节**的 P5-A3 要求「追加**模板自己的** `when == "body_fat_over"` 的
  addon」，并给出追加口径表：`exercise_name` / `video_url` / `impact_level` 「从
  `exercises[addon.module]` 取」、`sessions_per_week` = `template.weekly_frequency`。
  而 `TrainingPackage` 的字段是 `template_id` / `template_version` / `weeks` /
  `assembly_snapshot` / `paused` —— **`addons` 与 `weekly_frequency` 一个都没有**
  （`template_id` 是一个字符串，拿它反查模板需要注入模板映射，那也是一个新形参）。
  等价替换同样需要动作库：替身的 `exercise_name` / `video_url` / `impact_level`
  只能从 `ExerciseSpec` 取（P5-A8：读**源**，不读模板里的冗余副本）。
  即**三个必需输入里有两个拿不到**，而 P5-A3 是 Critical 级更正，不实现它 12 个
  `muscle_low` addon 就仍是模板里的死数据。
* **我的替代方案**：`apply_safety(pkg, inp, eq, *, template: Template,
  exercises: Mapping[str, ExerciseSpec])`。三个位置参数与简报**逐字一致**，新增的两个是
  **keyword-only**（口径照 `assemble(…, *, exercises)`）。
* **我的方案的代价**：① 调用点（Task 6 的 `prescription_stage`）要多写两个实参——
  而它本来就持有这两样东西（它先调 `match_template` 拿到 `Template`、再调 `assemble`
  时已经传过 `exercises=`），故代价接近零；② `apply_safety` 的签名比简报长。
* **备选的备选（我否掉了）**：把 `addons` 与 `weekly_frequency` 塞进 `TrainingPackage`。
  否掉的理由：那会让「装配产物」与「装配输入」混在一个值对象里，且 Task 8 的读模型会看到
  **两份** `weekly_frequency`（模板一份、包一份）——正是 Global Constraint #3 要挡的形状。
* **落地位置**：`safety.py` 模块 docstring 的第一节（标题逐字是
  「⚠️⚠️ 签名比简报多了两个 keyword-only 形参（实现者顶回控制者的一处矛盾）」），
  以及 `test_prescription_safety.py` 模块 docstring 的第一节。

#### 关切 2（Critical）：`apply_overrides(pkg, records)` 这个签名**实现不了 `SUBSTITUTE_EXERCISE`**

* **哪条决定**：简报 5.4 的 `Produces` 段写 `apply_overrides(pkg: TrainingPackage,
  records: Sequence[OverrideRecord]) -> TrainingPackage`。
* **为什么错**：五种 kind 里的 `SUBSTITUTE_EXERCISE` 要换掉一个动作，而 `AssembledBlock`
  的 `exercise_name` / `video_url` / `impact_level` 三个字段**只能从动作库取**。
  只换 `exercise_ref` 而留着旧动作的名字与视频 URL 是一个**看起来正常的谎**
  （学生端扫二维码看到的是间歇跑的视频、而处方上写着快走），把三个字段留空则是
  另一种谎（学生端看到一格空白）。两者都不可接受，而这两个字段的所有者是
  `exercises.yaml`（P5-A8），不在包里。
* **我的替代方案**：`apply_overrides(pkg, records, *, exercises: Mapping[str, ExerciseSpec])`。
  **不做成可选缺省 `None`**：那会让「传了 `SUBSTITUTE_EXERCISE` 却忘了传 `exercises`」
  变成一个只在**那一条记录**上才炸的 `TypeError`，离真因隔一层。
* **我的方案的代价**：只有 `SUBSTITUTE_EXERCISE` 用它，另外四种 kind 的调用点也要多传一个
  实参（一致性换安全性，我认为值得）。
* **落地位置**：`override.py` 模块 docstring 的第二节，以及 `test_prescription_override.py`
  模块 docstring。

### 5.2 我认为计划错了、但**没有**顶回（按派单照办 + 记录）的地方

#### 关切 3（Important）：`weekly_volume_base` 是**混合量纲**的

* **事实**：简报 5.2 第 6 步要求 `weekly_volume_base` 是「未乘个体系数、未乘 `week_deltas`
  的周量总和（`float`，`round(…, 1)`）」。而**同一节**的 P5-A1 立了一条理由：
  「**两种单位不可通约** → `volume_unit` 是必需字段…一个裸 `float` 无法回答
  『38.4 是分钟还是次数』，那会让 spec §4.3 的可追溯性断在这一环」。
  这两条互相打脸：`RED-END-ABN-01` 的 `weekly_volume_base` 实测是 **`168.0`**，
  它是 `48.0 min + 120.0 reps` —— 正是 P5-A1 说「不可通约」的那两种单位相加。
* **我的处置**：**按简报的字面契约实现**（`float`、`round(…, 1)`、12 个键一个不多），
  但把这件事**响亮地写进** `assembler.py` 模块 docstring 的「守不住什么」一节与
  `test_prescription_assembler.py` 的模块 docstring，并在 `AssembledBlock` 的字段注释里
  指明「可追溯性靠的是每个 block 自己那一对 `(weekly_volume, volume_unit)`」。
* **为什么没顶回**：它不会让生产码错（今天没有任何消费者读这一格）、不会让守卫假绿、
  也**不会让数据不可追溯**——每个 block 的 `(weekly_volume, volume_unit, sessions_per_week)`
  加上快照里的 `volume_factor` / `week_deltas` 足以离线复算到 **block 粒度**，
  `weekly_volume_base` 只是一个粗粒度的合计。按 Ruling 145，这属于「记进报告、不单独返工」。
* **建议的替代方案（给 Task 9 / spec §14）**：把这一格改成 `Mapping[str, float]`
  按单位分列（`{"min": 48.0, "reps": 120.0}`），**键数仍是 12**（只是这一格的值从 `float`
  变成 `dict`），JSON 可序列化性不变。代价：`assemble` 的那条「值逐字段相同」的复现测试要
  改成深比对（今天已经是深比对，故实际代价为零）。

#### 关切 4（Important）：加载器不校验 `structure` 的**值类型**，装配器按派单也不校验 → 有一条静默错值的路

* **事实**：`app/refdata_prescription._structure` 只查两件事——「是个非空映射」与
  「键全是字符串」，**不查值是不是数字**（它自己的 docstring 逐字写着「⚠️ **键集不受约束**…
  只查两件事」）。简报 P5-A1 又要求装配器「**不重复校验键的类型**（单一所有者）」。
  两条合起来的后果：一份 `structure: {sets: "4", work_min: 3, rest_min: 2}` 的模板 YAML
  **能加载成功**，然后在 `_base_volume` 里得到 `float(3 * "4")` = `float("444")` =
  **`444.0`** 这个静默错值（`sets` 与 `work_min` **都是**字符串时反而 `TypeError`、是响的）。
* **为什么这是 Important 而不是 Critical**：它需要一份**混合类型**的坏 YAML，而
  PyYAML 对 `sets: "4"`（带引号）才会给出字符串——专家手写时更可能写 `sets: 4`。
  且 18 套模板今天全部是整数（亲扫：78 个 `{4, 3, 2}` + 52 个 `{3, 10}`，无一例外）。
* **我的处置**：**照派单办**（装配器不校验值类型），把这条路的完整机制写进
  `assembler.py` 模块 docstring 的「守不住什么」与 `test_prescription_assembler.py`
  的模块 docstring。**修法在加载器**（`_structure` 里加一句「值必须全是 `int`/`float`
  且不是 `bool`」），而 `app/refdata_prescription.py` **不在派单的文件清单里**，
  故本 Task 无权改它。
* **建议**：Task 9 的勘误轮次给 `_structure` 补这一句（约 6 行 + 1 条测试），
  或在计划里显式承认「`structure` 的值类型不被任何一层校验」。

#### 关切 5（Minor）：`EquivalenceTable.lookup` 不按 `when` 过滤

* **事实**：`lookup(ref, impact_ceiling)` 只按 `from_ref` 与 `IMPACT_RANK[max_impact]`
  过滤，**不看 `mapping.when`**。真表里两个触发（`bmi_over_30` / `muscle_low_p10`）的替身
  **逐条相同**（`exercise_equivalence.yaml` 的注释逐字写着「替身与触发 1 相同：spec 原文
  就是『同上』」），故今天**无影响**。
* **将来会怎样**：若专家给两个触发配了**不同**的替身（完全可能：肌肉量偏低的学生更适合
  抗阻类替身、BMI 超标的更适合卸载体重的有氧类替身），`lookup` 会返回**书写顺序里的第一条**，
  而 `Substitution.trigger` 会记成另一个触发 —— 一个**静默的**错配。
* **我的处置**：不改 `lookup`（它是 Task 2 的产物、有它自己的守卫与指纹，改它要连带改
  `tests/test_refdata_prescription.py` 与 `tests/domain/test_prescription_exercises.py`，
  超出派单范围）。把这条写进 `safety.py` 模块 docstring 的「守不住什么」。
* **建议**：Task 9 或 Plan 03 给 `lookup` 加一个可选的 `when` 形参（默认 `None` = 不过滤，
  保持既有调用点不变），并加一条守卫钉住「`when` 非 `None` 时只返回该触发的映射」。

#### 关切 6（Minor）：`INTENSITY_STEP` 对 106/130 个 block **静默无事发生**，而 `apply_overrides` 没有 warning 通道

* **事实**：`AssembledBlock` **不保存** `Intensity`（只保存渲染好的 `intensity_text` 与
  `hr_zone`），故「调整强度档位」今天**只能**作用在目标心率区间上。真仓 130 个 block 里
  **106** 个是 `hr_zone is None`（`none` 82 + `onerm_pct` 24），对它们 `INTENSITY_STEP`
  原样返回。而 `apply_overrides` 的返回类型是 `TrainingPackage`（简报定的），
  **没有 `warnings` 通道**能把「你这条覆盖对 3 个 block 里的 2 个没生效」说出来。
* **对比**：5.3 的 `SafetyOutcome` **有** `warnings`，正是为了「没做也要留痕」。
  覆盖侧缺这一层，是简报 5.4 的 `Produces` 只给了 `TrainingPackage` 的直接后果。
* **我的处置**：不改返回类型（那会破坏简报的契约、且 Task 6 要按它落库），
  把这条写进 `override.py` 模块 docstring 的「守不住什么」。
  **留痕做在能做的地方**：`INTENSITY_STEP` 命中时会在 `intensity_text` 后面追加
  「｜教师覆盖：强度 −5 个百分点，目标心率 107–127 bpm」，于是**改了的**那一档在包内可见。
* **建议**：Task 8 的教师端在提交 `INTENSITY_STEP` 之前**前置检查**目标动作有没有
  `hr_zone`（前端能拿到训练包），或 Task 9 给 `apply_overrides` 加一个可选的
  `warnings: list` 出参。

#### 关切 7（Minor）：addon `module` 悬空时 surfaces 成 `KeyError` 而不是 `ValueError`

* 简报明写「**Task 3 的加载器已校验过它存在**，故这里**不重复校验**——单一所有者」，
  我照办（`exercises[addon.module]`）。于是那一档抛的是 `KeyError`，
  与 `assemble` 那三道 `ValueError` **异常类型不一致**。响亮，但不统一。
  已写进 `safety.py` 的「守不住什么」。

### 5.3 我没按派单做的地方

**0 处静默偏离。** 三处「与派单字面不同」的处置全部在上面显式写明：

1. **两处签名扩参**（关切 1、关切 2）——都是 Critical 级顶回，理由、替代方案与代价齐备，
   且**位置参数与简报逐字一致**、新增的一律 keyword-only。
2. **`hrmax` 对 `measured` 那一档也校验 `age`**（第 2.3 节 5.1 的第 2 条）——派单那句
   「校验后直接返回」有歧义，我按「年龄校验是独立的一句」读，且这是**更安全**的那一半
   （Review Focus 第 4 条的立意）。派单文本本身也支持这个读法。
3. **`weekly_volume_base` 按简报字面实现（混合量纲）**，没有擅自改成 `Mapping`
   （关切 3）——即这一处我**服从**了派单、只记录异议。

另外三处「派单没给、我定了口径」的地方，都在第 2.3 节逐条写明并配了守卫：
`Substitution` / `warnings` 的粒度、`safety_skipped` 的三个 token 与「没有
`body_fat_missing`」的不对称、`assembly_snapshot` 里 `as_of` 与 `week_deltas` 的 JSON 化类型、
五种 `OverrideKind` 的具体语义。

---

## 6. 公开面变化

| 项 | Task 4 结案（`c8e26b8`） | Task 5 结案（`fc8f5a8`） |
|---|---|---|
| `app.domain.prescription.__all__` | **24** | **43**（+19） |
| `_PRESCRIPTION_PUBLIC_BASELINE` | 24 个 `(名字, 所有者模块)` 二元组 | **43** 个 |
| 那句 `assert len(_PRESCRIPTION_PUBLIC_BASELINE) == 24` | 24 | **已同步改成 43**（含它的报错文案「基线是 43 个名字，抄漏了就当场红」） |
| 那句 `assert len(set(names)) == 24`（派单没点到的第二句） | 24 | **已同步改成 43** |
| `_OWNED_MODULES`（派单没点到的第三处） | 3 个模块 | **7** 个模块 |
| 支 3（`sorted(names) != names`，声明序不是字母序） | 绿 | **仍绿**（43 项仍非字母序） |
| 支 5（穷尽：公有顶层定义 == 基线里该所有者的名字集） | 对 3 个模块成立 | **对 7 个模块成立** |
| 支 6（红输入反面对照） | 绿 | **仍绿**（哨兵名与「少最后一个」两种合成失同步态都判不相等） |

**新增的 19 个名字与各自的所有者**（声明序 = `__init__.py` 里 `__all__` 的书写序 =
各模块里的书写序）：

| 所有者 | 个数 | 名字 |
|---|---|---|
| `app.domain.prescription.intensity` | **3** | `hrmax`、`hr_zone`、`age_from` |
| `app.domain.prescription.assembler` | **8** | `VOLUME_UNITS`、`VOLUME_FACTOR_BANDS`、`StudentProfile`、`AssembledBlock`、`AssembledSession`、`AssembledWeek`、`TrainingPackage`、`assemble` |
| `app.domain.prescription.safety` | **4** | `SafetyInput`、`Substitution`、`SafetyOutcome`、`apply_safety` |
| `app.domain.prescription.override` | **4** | `OverrideKind`、`OverrideRecord`、`apply_overrides`、`summarize_overrides` |

**19 这个数是亲扫出来的、不是数出来的**（P5-A13 / 硬规矩 #80 的处置）：用与
`_public_top_level_definitions` **同一个 AST 口径**扫四个文件，得
`intensity 3 / assembler 8 / safety 4 / override 4`，`3 + 8 + 4 + 4 = 19`，`24 + 19 = 43`；
改完基线之后 `test_prescription_public_namespace_is_pinned_verbatim` 的**六支全绿**，
即支 5 的「穷尽」判据独立复核了这个数（两侧不同源：期望侧是字面基线、实际侧是 AST 扫源码）。

**刻意不进公开面的私有名**（都带前导下划线，故支 5 的 AST 口径数不到它们）：
`intensity` 的 `_TANAKA_INTERCEPT` / `_TANAKA_SLOPE` / `_AGE_MIN_EXCLUSIVE` /
`_AGE_MAX_EXCLUSIVE` / `_MEASURED_MIN` / `_MEASURED_MAX`；
`assembler` 的 `_DURATION_KEYS` / `_REPS_KEYS` / `_ENDURANCE_LOW_CUTOFF` /
`_ENDURANCE_MID_CUTOFF` / `_BAND_FACTOR` / `_SEX_FACTOR` / `_NO_INTENSITY_TEXT` /
`_HRMAX_FORMULA` / `_base_volume` / `_render` / `_volume_factor`；
`safety` 的 `_BMI_LIMIT` / `_TRIGGER_MAP` / `_ADDON_INTENSITY_TEXT` / `_MUSCLE_LOW_WARNING` /
`_SKIP_BMI` / `_SKIP_MUSCLE_MASS` / `_SKIP_MUSCLE_P10`；
`override` 的 `_rebuild` / `_weekly_frequency` / `_substitute` / `_intensity_step` /
`_volume_scale`。

**理由**（已写进 `test_refdata_prescription.py` 的 `_OWNED_MODULES` 注释与
`__init__.py` 的 docstring）：三档个体修正系数、BMI 阈值、`_TRIGGER_MAP` 的跨表翻译都是
**待专家确认的工程约定**（spec §14 #32 / #28）或**内部实现**，把它们做成公开契约会让
「专家调阈值」看起来像一次破坏公开面的改动。而 `VOLUME_UNITS` 与 `VOLUME_FACTOR_BANDS`
**进了**公开面，因为它们是**词表**（取值域），本仓的既有纪律是词表有唯一所有者且公开
（`ADDON_TRIGGERS` / `INTENSITY_TYPES` / `TEMPLATE_LAYERS` / `EQUIVALENCE_TRIGGERS` /
`IMPACT_RANK` / `TARGET_DOMAIN` 六个先例）。

**`Layer` 仍是唯一一个「借来的」名字**（所有者 `app.domain.stratify`），Task 5 没有新增
「借来的」名字：`Sex`（`StudentProfile.sex` 的类型）是从 `app.domain.indicators` **import**
进 `assembler.py` 的，但它**不是** `assembler` 的公有顶层定义（AST 口径只数
`class` / `def` / 赋值），故支 5 不要求它被第二次重导出——这一层推理已写进
`_OWNED_MODULES` 的注释。

---

## 7. 扫描面变化

**28 → 32**，与简报 P5-A13 后面那段「扫描面复核」的预测**逐格相符**。

复核命令（在**仓库根**跑，与 `tests/architecture/test_layering.py` docstring 里那一条逐字相同）::

    python -c "import pathlib,collections; c=collections.Counter(p.parts[2] for p in pathlib.Path('backend/app').rglob('*.py') if p.parts[2] in ('pipeline','db','domain')); print(sorted(c.items()), sum(c.values()))"

| 时点 | `db` | `domain` | `pipeline` | 合计 |
|---|---|---|---|---|
| 基线 `e26347f`（Plan 01） | 4 | 6 | 7 | 17 |
| Task 1 拆包后 `ad1d190` | 11 | 6 | 7 | 24 |
| Task 3 结案 `3473dc6` | 11 | 9 | 7 | 27 |
| Task 4 结案 `c8e26b8` | 11 | **10** | 7 | **28** |
| 5.1 后 `d78120a` | 11 | 11 | 7 | 29 |
| 5.2 后 `1c5b9bb` | 11 | 12 | 7 | 30 |
| 5.3 后 `5f05dda` | 11 | 13 | 7 | 31 |
| **5.4 后 `14673aa` = 5.5 后 `fc8f5a8`** | **11** | **14** | **7** | **32** |

`domain` 那 **14** 个 = `__init__` / `derive` / `indicators` / `percentile` / `stratify` /
`tables`（Plan 01 的 6 个）+ `prescription/{__init__, exercises, templates, match}`（Task 2–4
的 4 个）+ `prescription/{intensity, assembler, safety, override}`（**本 Task 的 4 个**）。

### 7.1 架构守卫**不需要改**（一个字都没改）

两份守卫全绿，且**没有任何一处需要跟着扫描面涨而修改**——三个下界都仍是「下界」而不是
「实测值」，这正是它们的作者当初刻意不写死实测值的收益：

| 守卫里的断言 | 下界 | 本 Task 后的实测 | 余量 |
|---|---|---|---|
| `test_domain_purity._assert_not_empty`：`len(scanned) >= 5` | 5 | **14** | 2.8× |
| `test_layering`：`len(scanned) >= 8` | 8 | **32** | 4.0× |
| 两份守卫各自的 `test_absolute_folding_matches_resolve_name`：`len(real_py) >= 40` | 40 | **77**（`backend/` 下全部 `.py`） | 1.9× |
| 同上：`relative_seen >= 16` | 16 | **30**（Task 4 结案时是 18；本 Task **净增 12** 条：`prescription/__init__.py` 3 → **7**（+4：`.assembler` / `.intensity` / `.override` / `.safety` 四句）、`assembler.py` 0 → **3**（`.exercises` / `.intensity` / `.templates`）、`safety.py` 0 → **3**（`.assembler` / `.exercises` / `.templates`）、`override.py` 0 → **2**（`.assembler` / `.exercises`）；⚠️ **`intensity.py` 一条都没有**——它**一个模块级 import 都没有**，见第 2.3 节 5.1 的第 1 条） | 1.9× |
| 同上：`folded` 里必须出现的 5 个字面串 | 5 个 | 5 个都在（另**新增折出 4 个串**：`app.domain.prescription.intensity` / `.assembler` / `.safety` / `.override`；`.exercises` / `.match` / `.templates` 三个自 Task 2–4 就在） | — |

⚠️ **`level == 2` 的相对导入到今天仍然不存在**（账本 Ruling 104 记的同一件事）：
本 Task 的四个模块全部沿用 Task 2–4 的选择——**跨包指向所有者用绝对串**
（`from app.domain.indicators import Sex`）+ **同包兄弟用 `level == 1` 相对串**
（`from .intensity import …`）。故两份守卫矩阵里
`("indicators", 2, ("app", "domain", "prescription"), "X", "GREEN")` 那一格
**到本 Task 之后仍是「前瞻」、不是真仓形状**。这一点值得在 Task 9 清扫时复核一次：
它已经「前瞻」了三个 Task。

⚠️ **`FORBIDDEN_IO` 的子串黑名单与四个新模块的 docstring 擦肩而过**：那四个文件的散文里
出现了 `datetime`、`math`、`import datetime`、`get_type_hints` 这些词（都是在解释
「为什么**不**用它们」），而 `FORBIDDEN_IO` 的 14 个子串里**一个都没撞上**
（`Path(` / `import os` / `__file__` / `json.load` / `.read_text` …）。这正是
`test_domain_has_no_clock_or_file_access` 从子串改成 AST 节点匹配的收益（它的 docstring
逐字写着「**误报没了**（真收益）：…Plan 01 因此**不敢在 domain 的散文里写这些词**——
那是让守卫反过来审查文档」）。⚠️ 但**第三条守卫仍是子串匹配**，故本 Task 的四个新模块
在散文里刻意**没有**写 `Path(`、`__file__`、`import os` 这几个串（`intensity.py` 的
docstring 提到 `datetime` 与 `math` 是安全的，它们不在 `FORBIDDEN_IO` 里）。
**这一条是「实现者要注意的约束」，不是缺陷**，记在这里免得 Task 6–9 踩。

---

## 附：本 Task 交付的文件清单

**新建（生产，4 个，全在 `backend/app/domain/prescription/`）**

| 文件 | stmts | branch | 覆盖率 |
|---|---|---|---|
| `intensity.py` | 27 | 12 | 100% |
| `assembler.py` | 124 | 38 | 100% |
| `safety.py` | 96 | 40 | 100% |
| `override.py` | 96 | 38 | 100% |

**新建（测试，4 个，全在 `backend/tests/domain/`）**

| 文件 | 测试数 |
|---|---|
| `test_prescription_intensity.py` | 10 |
| `test_prescription_assembler.py` | 26 |
| `test_prescription_safety.py` | 25 |
| `test_prescription_override.py` | 19 |

**修改（2 个）**：`backend/app/domain/prescription/__init__.py`（+78 行）、
`backend/tests/test_refdata_prescription.py`（+102 / −25 行）。

**未改**：`backend/data/` 下任何文件、两份架构守卫、`app/refdata_prescription.py`、
任何 Plan 01 的 domain 模块。

---

## 附 2：结案复核（5.5 commit `fc8f5a8` **之后**、变异取证**之后**的一次干净重跑）

变异取证会改写生产文件再还原，故结案前又跑了一次完整验收，确认还原是彻底的。

**① 四个生产模块的 sha256 与 M0 那一份逐字相同**（`python -c "import hashlib,pathlib; …"`
在仓库根跑，`backend/app/domain/prescription/*.py` 全部 8 个文件）::

    __init__.py    ed2d01b079e13c5679358dc7c4b848c5f6febb160d0443be0ca159e30273a91f
    assembler.py   d5e7890e13bf0d877b7bd3500f01a0cc343532b2f55e62cd468ed3d8d18894cc   ← 与 M0 一致
    exercises.py   7f079ff5e1a043caf04e73db8472a12831191147a9b0ec4c0623b7477ca23558
    intensity.py   9d8336d25a2df1967a02eb5629b2ec2252cff637b18ea9fd46d5264947c78e61   ← 与 M0 一致
    match.py       40e08f5587c92f46b7cd337e4d167494647951e392e08340989614f69c855bcd
    override.py    1e2e088c886b499034bf77f9abd442c7bfb36cf9a81832837d900ca98163b337   ← 与 M0 一致
    safety.py      bc471a4b5161d10c7006d69fa67ecd44eac5cda6722c7a304a84456900a8e108   ← 与 M0 一致
    templates.py   25963c89732125e14ae09ffe3dbd7c3602d4b253eb133d7b0bdf13cc4d06ec9a

（`__init__.py` / `exercises.py` / `match.py` / `templates.py` 四个不在 M0 的清单里：
前一个是 5.5 改的、后三个本 Task 一个字没动。）

**② `git status --porcelain` 在 5.5 commit 之后只剩控制者自己的 3 个未跟踪文件**
（`.superpowers/…/_mk_brief5.py`、`task-5-brief.md`、`task-5-report.md`）——
即**工作树与 `fc8f5a8` 逐字相同**，变异没有留下任何残余。
本报告按 Plan 01 的既有惯例**留给控制者一起入 `docs:` commit**，故没有自行 `git add`。

**③ 完整覆盖率重跑**（`cd backend; python -m pytest -q --cov=app.domain --cov-branch
--cov-report=term-missing`）::

    TOTAL                                    888      0    260      0   100%
    671 passed, 1 skipped in 137.89s (0:02:17)

与 5.5 commit 之前那一次（`888 / 0 / 260 / 0 / 100%`、`671 passed, 1 skipped in 134.65s`）
**逐格相同**，墙钟差 3.24 s（2.4%，同一台机器的正常抖动；⚠️ 这一列的分辨率低于它的噪声，
故只作「两次结果一致」的证据、不作性能断言——口径照 `tests/pipeline/test_backfill.py`
里那条按硬规矩 #42 主动 skip 的墙钟断言）。那个 `1 skipped` 的归属见第 2 节的表下注。

**④ 不带 `--cov` 的全量**（5.5 commit 之前亲跑，工作树与 commit 逐字相同）::

    672 passed in 66.96s (0:01:06)

**⑤ 禁区五个指纹**见第 1.4 节，全部与 Task 2/3 结案时逐字相同。

---

## Task 5 fix round 1

**基线** `fc8f5a8` → **本轮 2 个 commit**：`fe3a6df`（`fix: Plan02 Task5 fix round 1 的 F1-1/F1-2 —— weekly_volume_base 按单位分列 + rpe 值域改 0–10`）/ `f9b6ed5`（`docs: Plan02 Task5 fix round 1 的 F1-3/F1-4/F1-5 —— 撤回 P5-A10（控制者错误 #140）+ 硬规矩 #82/#83 入账 + 计划正文 11 处更正`）。
**分支** `feature/plan-02-prescription-engine`。**没 push、没切分支、没碰 main。**
**TDD**：F1-1 与 F1-2 都是先改测试跑到 **9 failed / 49 passed**（红的原因逐条是「`168.0` != `{'min': 48.0, 'reps': 120.0}`」「`'float' object is not iterable`」「`DID NOT RAISE ValueError`」，不是 import 错误），再改实现跑到全绿。

### 0. 一句话结论

5 项全部落地。全量 **672 → 679 passed**（不带 `--cov`）/ **678 passed, 1 skipped**（带 `--cov`）；覆盖率四格 **888/0/260/0 → 905/0/262/0/100%**；公开面 `__all__` **43 → 43**；扫描面 **32**；三个禁区指纹逐字不变；`backend/data/` 一个字节没动。计划正文 **151 467 B / 938 行 → 159 408 B / 939 行**；账本 **336 427 B / 2 153 行 → 346 910 B / 2 214 行**。
**顶回控制者 6 处**（第 7–12 次），见 §9；**没按派单字面做的 7 处**，见 §8。

### 1. F1-1（Critical）`weekly_volume_base` 从混合量纲改成按单位分列的只读 Mapping

#### 1.1 新类型与那个例子的逐字面值（**期望值自己算**，硬规矩 #44）

| 项 | 改前 | 改后 |
|---|---|---|
| 类型 | `float` | **`Mapping[str, float]`**（运行时是私有的 `_ReadOnlyVolumeBase`，`dict` 的子类，MRO = `[_ReadOnlyVolumeBase, dict, object]`） |
| `RED-END-ABN-01`（男 20 岁、`endurance_score=50`）那一格 | `168.0` | **`{"min": 48.0, "reps": 120.0}`** |
| 快照键数 | 12 | **12**（键名与键序一个字没动，`test_assembly_snapshot_keys_are_exactly_the_pinned_set` 仍全绿） |

**我自己算的过程**（不复用 `assembler.py` 的任何代码；探针 `t5_probes/_fr1_recompute_volume_base.py` 直接读 `backend/data/prescription/*.yaml`，自己数 `sessions_per_week`、自己做乘法）：

```
RED-END-ABN-01：weekly_frequency = 4、sessions = 4、
                per_ref = {interval_run: 4, compound_circuit: 4}
  interval_run      structure {sets:4, work_min:3, rest_min:2}
                    base = work_min × sets = 3 × 4 = 12 min/课
                    min 档 = 12 × 4 课 = 48.0        （= base × sessions_per_week）
  compound_circuit  structure {rounds:3, reps:10}
                    base = rounds × reps = 3 × 10 = 30 reps/课
                    reps 档 = 30 × 4 课 = 120.0
  → {"min": 48.0, "reps": 120.0}      48.0 + 120.0 = 168.0 = 改前那个混合量纲的数 ✓
```

**与控制者派单里那个分解逐格相符**（派单自己写的「它是 `48.0 min + 120.0 reps` 相加的结果」），故不存在「先怀疑自己还是先怀疑派单」的分歧。

顺带亲算了另外两套，用来证明**键集不是硬写死的**（它们各只有一个单位）：
`GRN-END-NOR-14`（绿、2 课 × 2 个 12 min）= **`{"min": 48.0}`**；`YEL-STR-ABN-09`（黄、3 课 × 2 个 30 reps）= **`{"reps": 180.0}`**。
⚠️ 绿层那套的 `min` 档**恰好也是 48.0**，与红层同值而来源完全不同（2 课 × 2 个 12 min 对 4 课 × 1 个 12 min）——这正是「按单位分列」比「一个总数」信息量大的地方。

**18 套的键集分布**（探针独立算出、字面写死进测试）：
`{("min",): 10, ("reps",): 6, ("min", "reps"): 2}`——**16/18 套只有一个单位**，只有 `RED-END-ABN-01` / `RED-END-NOR-02` 两个都有。`"unspecified"` **0 次出现**（`assemble` 跑在 `apply_safety` 之前，那时还没有 addon block），与派单的预期一致。

#### 1.2 `types` 是否被守卫放行 —— **实测：不放行**

探针 `t5_probes/_fr1_probe_types_json.py`，做法是**真的把 `import types` 插进 `assembler.py`**（插在 `from collections import Counter` 上面一行）再跑守卫，跑完 `write_bytes(original)` 逐字节还原，并按**硬规矩 #83** 在每次跑测试前 `shutil.rmtree(__pycache__)` + 子进程设 `PYTHONDONTWRITEBYTECODE=1`：

```
[对照 M0：未插 import types] exit=0   4 passed in 0.22s
[变异 M1：插了 import types] exit=1   1 failed, 3 passed in 0.37s
  FAILED tests/architecture/test_domain_purity.py::test_domain_imports_stay_within_the_allow_list
  AssertionError: app/domain 是叶子层，import 必须落在白名单内
    （['collections', 'collections.abc', 'dataclasses', 'enum', 'numpy', 'typing'] + app.domain.*）：
      assembler.py:148: types
[还原] sha256 相同 = True（31817 B）
```

→ **`types` 不放行**，故 `types.MappingProxyType` 在 domain 里拿不到。**不改守卫**：往 `ALLOWED_MODULES` 加模块是扩大 domain 可用面的架构决策，与 P5-A4 拒绝 `math`、Task 3 拒绝 `datetime` 同一条纪律。

#### 1.3 JSON 序列化测试（**派单说这是本轮最容易漏的一条**）

两条，都在 `allow_nan=False` 下：

| 测试 | 位置 | 钉的是什么 |
|---|---|---|
| `test_assembly_snapshot_is_json_serialisable` | `tests/domain/test_prescription_assembler.py` | `assemble` 直出的 **12** 键整个能 `json.dumps(snap, allow_nan=False)`；序列化文本里逐字含 `"weekly_volume_base": {"min": 48.0, "reps": 120.0}`、**不含** `168.0`；round-trip 之后 12 个键名与序不变；`endurance_score is None` 那一档序列化成 `null` 而不是 `NaN`；round-trip 之后那一格是**普通 `dict`**，改它**不会**回写进程内的快照 |
| `test_the_safety_snapshot_is_json_serialisable` | `tests/domain/test_prescription_safety.py` | `apply_safety` 之后那 **15** 键（= 12 + 3）整个能 JSON 化。⚠️ **这一条比上一条更承重**：Task 6 落进 `prescription.assembly_snapshot` 那个 `JsonText` 列的是**安全后置之后**的快照。挑的是三个触发全命中那一档，于是 `safety_volume_factor` 是 `0.8 × 0.9` 的**未 round 乘积** `0.7200000000000001`（P5-A6）——序列化文本里逐字出现，证明「不 round 系数」这个决定不会在落库时炸 |

**结论：两条都通过。**`JsonText.process_bind_param` 用的正是 `json.dumps(value, ensure_ascii=False)`（不带 `default=`），所以「`json` 默认能不能认它」就是真判据，不是理论问题。

#### 1.4 落地的构造为什么是「屏蔽 mutator 的 `dict` 子类」（三条亲跑取证）

派单给的决策树是「`types` 红 → 改用 `collections.abc.Mapping` 标注 + 一个不可变的构造」「若 `MappingProxyType` 序列化失败 → 就在快照里存 `dict`，只读性靠约定」。**这两条备选我都实测了，都不成立**，最后落的是第三个构造：

```
② json.dumps({"weekly_volume_base": types.MappingProxyType({"min": 48.0, "reps": 120.0})})
   → TypeError: Object of type mappingproxy is not JSON serializable
   isinstance(proxy, dict) = False
③ 屏蔽 mutator 的 dict 子类：
   isinstance(m, dict) = True
   json.dumps 成功: {"weekly_volume_base": {"min": 48.0, "reps": 120.0}}
   m['min'] = 0 / del / update / pop / popitem / clear / setdefault → 全部 TypeError
   m == {'min': 48.0, 'reps': 120.0} → True     （故整快照的 == 字面断言仍可用）
   {**m} → 普通 dict                            （故 apply_safety 的 {**snap, …} 仍产出普通外层）
```

`collections.abc.Mapping` 的自定义子类**同样不在 `json` 的默认类型表里**（`json` 只认 `dict` 及其子类），故派单的第一条备选走到头还是落到第二条备选（存 `dict` + 只读性靠约定），而那会让派单同时要求的测试③（`pytest.raises(TypeError)`）**无法成立**。`dict` 子类是两条约束唯一的交集，故没有走 fallback。→ **顶回，见 §9 第 2 条。**

⚠️ **两个实测撞出来的坑**（都已修、都有守卫，也都写进了 `assembler.py` 的 docstring）：

* **`|=` 必须单独挡**：`dict.__ior__` 是 C 实现、**绕过**被覆盖的 `update`。  亲跑：只挡 7 个 mutator 时 `m |= {"reps": 120.0}` **未抛**、`m` 真的变成了 `{'min': 48.0, 'reps': 120.0}` ——那就是「看起来只读、其实一改就穿」。  故 `_ReadOnlyVolumeBase` 挡的是 **8** 个入口：`__setitem__` / `__delitem__` / `pop` / `popitem` / `clear` / `update` / `setdefault` / `__ior__`。
* **屏蔽 `__setitem__` 会顺手打断 `copy`**：亲跑，没有 `__reduce__` 时 `copy.copy(m)` 抛 `TypeError`，栈里是 `copy.py:301 y[key] = value`——`copy._reconstruct` 正是靠逐项赋值重建的。`TrainingPackage` 是 frozen dataclass，Task 6/8 完全可能对整包 `deepcopy`，那时一个会炸的只读映射就是埋好的地雷。故给它一个 `__reduce__`（`(_ReadOnlyVolumeBase, (dict(self),))`），`copy` / `deepcopy` / `pickle` 三条路径一次修好（亲跑：三者都返回**同类型、同内容、不同身份**的新对象）。守卫是 `test_weekly_volume_base_survives_copy_and_pickle`。

⚠️ **`m.__init__({...})` 重调仍能改内容**（亲跑未抛）：这是 `dict` 子类做不到「构造后彻底封死」的那一格。没挡它，因为挡了就没法构造；如实记录为能力边界（硬规矩 #39），守卫也不假装覆盖它。

⚠️ **只读性只在进程内成立**：落进 JSON 列再读回来就是普通 `dict`、可变的了。这不是缺陷而是事实，`test_assembly_snapshot_is_json_serialisable` 里**显式断言**了「round-trip 之后类型是 `dict`」并证明改它不会回写进程内的快照。

#### 1.5 为什么做成**私有**（`__all__` 43 → 43）

`tests/test_refdata_prescription.py::test_prescription_public_namespace_is_pinned_verbatim` 的**支 5** 要求「七个 `_OWNED_MODULES` 的**公有**顶层定义与 `_PRESCRIPTION_PUBLIC_BASELINE` 互为充要」。做成公有就要同步改 `__all__`、那份基线与它的两句 `assert … == 43`（43 → 44），而派单 F1-1 没有要求扩公开面。故类名带前导下划线（`_ReadOnlyVolumeBase`），支 5 数不到它，**三处一个字都没动**。消费者看到的就是一个「改不动的 `dict`」。

#### 1.6 实现口径与派单口径的一处差别（**顶回，见 §9 第 1 条**）

派单写「值 = 该单位下所有 block 的 `base × sessions_per_week` 之和」。**字面照做会算错**：若「所有 block」指遍历每个 `(session, block)` 实例，`RED-END-ABN-01` 会得到 `{"min": 192.0, "reps": 480.0}`（把课数乘了两遍），而派单自己把 `168.0` 分解成 `48.0 min + 120.0 reps`，说明它要的是**去重后**的那一份。

落地取的是**逐 `(session, block)` 累加 `base`**（改前的 `volume_base += base` 只是加了个分桶键），它与「去重后 `base × sessions_per_week` 之和」**逐格相等**——因为 `sum(base over 每一次出现) == base × 该 ref 的出现次数 == base × sessions_per_week`。探针对真仓 **18/18 套**做了两种口径的对拍，**全部相同**。选逐次累加是因为它对「同一 `exercise_ref` 在不同课里 `structure` 不同」这一档更稳健（那档下 `base × sessions_per_week` 得先挑一个 `base`，而挑哪一个没有答案；加载器不约束「同 ref 同 structure」）。今天真仓没有这一档。

#### 1.7 新增/改动的守卫清单（`+6` 条）

| 测试 | 新/改 | 钉什么 |
|---|---|---|
| `test_weekly_volume_base_is_split_by_volume_unit` | **新** | 派单要求的①：三套模板（红/绿/黄，各代表一种键集形状）的逐个字面值 + **键序** |
| `test_weekly_volume_base_keys_are_a_subset_of_volume_units` | **新** | 派单要求的②：真仓 18 套，键集 ⊆ `VOLUME_UNITS`、**不含 `"unspecified"`**、值全是 `float`、非空，且键集分布 == `{("min",): 10, ("reps",): 6, ("min", "reps"): 2}` |
| `test_weekly_volume_base_is_read_only` | **新** | 派单要求的③：`base["min"] = 0` 抛 `TypeError`，外加 8 个 mutator 逐个抛、8 次尝试后一个字没变 |
| `test_weekly_volume_base_survives_copy_and_pickle` | **新** | `copy` / `deepcopy` / `pickle` 三条路径都返回同类型同内容的**新**对象，且副本仍然只读 |
| `test_assembly_snapshot_is_json_serialisable` | **新** | 派单要求的④（12 键，`allow_nan=False`） |
| `test_the_safety_snapshot_is_json_serialisable` | **新** | 15 键（Task 6 真正落库的那一份） |
| `test_assembly_snapshot_keys_are_exactly_the_pinned_set` | 未改 | 键数仍是 **12**、键序不变 ✓ |
| `test_assembly_snapshot_values_are_the_independently_recomputed_literals` | 改 | 那一格的字面值 `168.0` → `{"min": 48.0, "reps": 120.0}`；整条 `==` 顺带钉住「只读映射能与普通 `dict` 字面量相等」（`dict.__eq__` 不看子类型） |
| `test_rest_min_is_not_counted_as_volume` | 改 | 末句 `== 168.0` → `== {"min": 48.0, "reps": 120.0}`，并**同时**对账变异前后两份（`rest_min` 2 → 20，两档都一个字不变） |

### 2. F1-2（Critical）`rpe` 的值域改成 **0–10**

#### 2.1 全仓扫 `6–20` / `6-20` / `Borg` 的命中清单与逐条处置

两份探针：`t5_probes/_fr1_scan_rpe.py`（**全仓**，含 `.superpowers/`，改前跑一次、改后跑一次，输出落盘在 `t5_probes/_fr1_scan_rpe.out.txt`）与 `t5_probes/_fr1_scan_narrow.py`（**只扫 `backend/` + `Document/`**，并自动判定每条是不是显式否定句）。

**为什么要两份**：全仓扫的改后结果被**取证件自己**污染了（`6–20` 从 8 命中涨到 39 命中，涨的 31 条全在 `.superpowers/` 的补丁脚本、commit 信息、账本追加节与本探针里，它们**必须**引用被撤回的写法才能说明改了什么）。故真正有意义的判据是**收敛扫描**：`backend/` + `Document/` 里每一处命中都必须是「这个标度是错的」的显式否定句。

**A. `6–20`（en dash）—— `backend/` + `Document/`：改前 3 处 → 改后 7 处，7/7 全是否定语境**

| # | 位置 | 改前/改后 | 处置 |
|---|---|---|---|
| 1 | `backend/app/domain/prescription/assembler.py`（`_render` 的 docstring） | 改前 1 处 | **改了**：原文是「`rpe` 是自觉受累程度（Borg 6–20；spec §8.2 的课堂快评写的是 0–10，两处口径不一致，已记进报告的待清扫清单）」——那是把 spec 讲成「自相矛盾」。改成「**0–10** 标度（**不是** Borg 经典的 6–20；出处逐字引在 `_RPE_MIN` 的注释里）」并补上「这是跨计划契约」那一段 |
| 2 | `backend/app/domain/prescription/assembler.py`（`_RPE_MIN` 的注释） | 改后新增 | **刻意保留 1 处显式否定**：这一格是值域的**唯一住址**，「不是 Borg 经典的 6–20」这句是挡「下一个人好心改回去」的那道闸 |
| 3 | `backend/app/domain/prescription/assembler.py`（`ValueError` 的消息） | 改后新增 | **刻意保留**：开发者真撞到这道拒绝时，看到的就是这条消息，它必须自己说清「不是那套标度」 |
| 4 | `backend/tests/domain/test_prescription_assembler.py`（`test_rpe_intensity_renders_text_without_an_hr_zone` 的 docstring） | 改前 1 处 | **改了**：与 #1 同型的改写 |
| 5 | `Document/2026-10-06-实施计划02-智能处方引擎.md`（P5-A5 的「更正」列） | 改前 1 处 | **改了**（补丁脚本的 **E7**）：值域改成 0–10、`value=13` → `value=7`，并把 spec 四处出处逐字引进去、点明「这是跨计划契约」。⚠️ 这一格是**错误的源头**（我上一轮就是照它写的），故必须改，否则 Plan 03 的实现者读到的还是那一套标度 |
| 6 | `backend/app/domain/prescription/intensity.py` | **0 处** | **不用改**：亲扫这个文件里 `6–20` / `Borg` 各 **0** 命中；它唯一提到 RPE 的是「§7.4 的安全后置与 §8.2 的课堂 RPE 快评是兜住过量的那两道」，没有值域断言 |
| 7 | `backend/app/domain/prescription/templates.py` | **0 处** | **不用改，而且它是本轮最有力的一条佐证**：`INTENSITY_TYPES` 的注释本来就逐字写着「`rpe` 的出处是 spec §8.2 的课堂快评 **RPE 0–10**」，`Intensity` 的字段表也写着「`rpe` | `value` | spec §8.2 的 RPE **0–10** 同一套语义」。故改前的 `assembler.py` **与它自己的上游矛盾** |

**B. `6-20`（连字符）—— `backend/` + `Document/`：改前 0 处 → 改后 0 处**

全仓那 **12**（改前）/ **32**（改后）条命中**全是假阳性**，逐类处置：

| 类 | 例 | 处置 |
|---|---|---|
| 行号区间 | `test_domain_purity.py:196-201`、`:2397-2402`、`:97-100` | **不用改**：子串 `6-20` 恰好落在 `19**6-20**1` 里，与 RPE 无关 |
| 日期区间 | `首日 2016-2026-1008` | **不用改**：`201**6-20**26` 的巧合子串 |
| 本轮取证件 | `_t5_fr1_plan_patch.py` 的 `TOKENS = ("6\u201320", "6-20", "Borg")` 与它的两道闸门断言 | **不用改**：那是尺子本身 |

**C. `Borg` —— `backend/` + `Document/`：改前 2 处 → 改后 5 处，5/5 全是显式否定句**

与 A 的 #1 / #2 / #3 / #4 / #5 是同样 5 个位置（每一处都是「**不是** Borg 经典的…或「原先写成 Borg 经典的那一套标度，**错了**」）。⚠️ 计划正文那一处**只有 1 次**：补丁脚本 E7 的正文里其余提及一律改用「**那套标度**」指代，好让「计划正文里 `6–20` 恰好 1 处、`Borg` 恰好 1 处」这道闸门可用（脚本里的 `after_hits == {"6–20": 1, "6-20": 0, "Borg": 1}` 断言亲跑通过）。

**D. 取证件（`.superpowers/`）里的命中一律不改**，逐条理由：
`_t5_preflight_patch.py:39`（控制者的预检补丁，**已入库的历史件**，改它等于改历史）、`task-5-brief.md:168`（本轮派单的抄本，历史件）、`task-5-report.md:478`（**我上一轮报告里那条「待清扫清单」的原文**，历史件；本节取代它，但按审计链的纪律不回头改旧报告）、`_fr1_scan_rpe.py` / `_fr1_scan_narrow.py` / `_t5_fr1_plan_patch.py` / `_fr1_commit1.py` / `_fr1_msg1.txt` / `_fr1_ledger_append.py` / `progress.md` 的追加节（本轮取证与入账，**必须**引用被撤回的写法才说得清改了什么）。

#### 2.2 `value=13` 改成了什么

`13` → **`7.0`**（`Intensity(type="rpe", value=7.0)`），断言的 `intensity_text` 随之从 `"RPE 13"` 改成 **`"RPE 7"`**。挑 `7` 而不是别的合法值有两个理由：① 它是 spec 自己的数（`YELLOW_CLASS_RPE_HIGH` = 「课堂 RPE 均值 **> 7** 分」，§13 的数据分布预期也写着「课堂 RPE 集中在 **5–7**」），故这一格同时是「渲染正确」与「值在 spec 的真实分布里」两件事的证据；② `7` 渲染成 `"RPE 7"`（`%g`），不与 `hrmax_pct` 那档的「60–70% HRmax」串味。
另外 3 处跟着改：`assembler.py` 模块 docstring 的 Ruling 133 段（`Intensity(type="rpe", value=13.0)` → `value=7.0`）、计划正文 P5-A5 的「更正」列（E7）、计划正文 Step 1 的测试清单（E8）。

#### 2.3 加没加运行时校验 —— **加了**，理由四条

落地：`_render` 的 `rpe` 那一支新增一道 `[0, 10]`（两端**闭**）的拒绝，私有常量 `_RPE_MIN = 0.0` / `_RPE_MAX = 10.0`，消息里带**实际收到的值**与 spec 的四处出处。守卫 `test_rpe_value_outside_zero_to_ten_is_rejected`，四个值 **`-0.1` / `0.0` / `10.0` / `10.1`**（两端合法、两侧越界；`0.0` 与 `10.0` 断言渲染成 `"RPE 0"` / `"RPE 10"`）。亲跑另加两格：`7.0` → `"RPE 7"`、`13.0` → `ValueError`。

1. **它与 `hr_zone` 对称**：`intensity.hr_zone` 里**本来就有**一道 `0 <= low <= high <= 100` 的值域拒绝（`hrmax_pct` 那一档）。改前 `_render` 的 docstring 写的是「本函数**只渲染、不校验值域**：值域的校验属于加载器」——那句话**与本仓已有的做法自相矛盾**：`hrmax_pct` 的值域就在 domain 这一层被守着。故「单一所有者」在这里不是不加的理由，加了才是对称的。
2. **加载器确实不校值域**：`app/refdata_prescription.py` 的 `_INTENSITY_FIELDS` 只映射「哪一种 `type` 该有哪几个字段」（`"rpe": ("value",)`），校的是**字段形状**、不是取值。故没有本条的话，一份 `intensity: {type: rpe, value: 13}` 的 YAML **能加载成功**、渲染成学生端的「RPE 13」——在 0–10 标度上那是**一个看起来完全正常的谎**，正是本计划反复惩罚的失效形态。
3. **可证明不会让任何真仓模板炸**（派单要求的证明）：`rpe` 在 18 套模板里出现 **0** 次（P5-A5 亲扫：`none` 82 / `hrmax_pct` 24 / `onerm_pct` 24，共 130）。本轮另跑了一遍全量 **679 passed**，18 套模板的装配测试一条没红。故这道拒绝今天在生产路径上**不可达**，只有那一条边界测试走它（覆盖率仍是 Miss 0 / BrPart 0，`+2` 个 branch 就是它）。
4. **spec §14 那条待确认事项不构成反对理由**：它记的是「大屏阈值 RPE > **8** 与预警规则 RPE 连续 ≥ **9** 不一致」——那是两个**告警阈值**之间的矛盾，不是**标度**的矛盾。标度在 spec 里四处一致（0–10），故钉住 0–10 **不是**在替那条待确认事项做决定。

⚠️ **`onerm_pct` 与 `none` 两档仍不校验值域**（刻意不对称，理由写进 docstring）：前者的百分比合法性是加载器与 `EquivalenceTable` 的账，且 spec §7.2 只给了 `70` 一个例子、**值域无出处**（编一个 `[0, 100]` 就是替专家做决定）；后者没有标量。

### 3. F1-3（Important）撤回 P5-A10

#### 3.1 补丁脚本的逐条命中清单

脚本 `.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/_t5_fr1_plan_patch.py`（**已入库**）。纪律照硬规矩 #79：**每一处替换都先 `assert` 命中次数**，两遍走（第一遍只 assert、第二遍才替换），任何一处不符就**整体不落盘**；另有四道落盘闸门。**没用编辑器工具碰 `Document/` 下的任何 md。**

```
改前：bytes=151467  CRLF=937  裸LF=0  lines(split)=938  splitlines=937
改前的 F1-2 扫描闸门：{'6–20': 1, '6-20': 0, 'Borg': 0}
E1    命中 1 次 ✓  （old  77 字 → new  353 字）   F1-3：P5-A10「更正」列整格重写为「撤回」
E2    命中 1 次 ✓  （old 204 字 → new  355 字）   F1-3：5.3 正文恢复可核的原文引用
E3    命中 1 次 ✓  （old  61 字 → new  255 字）   F1-5①：P5-A2 补明「按 block 计数加权」
E4    命中 1 次 ✓  （old  51 字 → new  542 字）   F1-5②：5.5 补 _OWNED_MODULES 3→7 + 第二句 assert
E5    命中 1 次 ✓  （old 100 字 → new  256 字）   F1-5③：5.3 的 Consumes 补 Template / ExerciseSpec
E6    命中 1 次 ✓  （old  65 字 → new  478 字）   F1-5④：5.5 补 --cov 与不带的 passed 差 1
E7    命中 1 次 ✓  （old 164 字 → new  933 字）   F1-2：P5-A5 的值域 0–10 + value=7
E8    命中 1 次 ✓  （old 112 字 → new  360 字）   F1-2：Step 1 的 value=7 + 新增边界测试名
E9    命中 1 次 ✓  （old  80 字 → new 1325 字）   F1-1：六步口径第 6 步改成分列的只读 Mapping
E10a  命中 1 次 ✓  （old  95 字 → new  622 字）   5.3 的 apply_safety 签名扩参
E10b  命中 1 次 ✓  （old  95 字 → new  393 字）   5.4 的 apply_overrides 签名扩参
追加型（闸门 ① 跳过、由闸门 ④ 接管）= ['E4', 'E5', 'E6']
改后的 F1-2 扫描闸门：{'6–20': 1, '6-20': 0, 'Borg': 1}
改后：bytes=159408  CRLF=938  裸LF=0  lines(split)=939  splitlines=938
字节增量 = 7941 B   行数增量 = 1     BOM = False
```

**四道落盘闸门**（全部亲跑通过）：① 替换型的旧串一律 **0** 命中（**追加型** `old in new` 的三条 E4/E5/E6 在这一道上天然不可能 0 命中——那正是「追加」的定义，故跳过并**逐条打印**是哪三条，由闸门 ④ 接管，免得「跳过」变成静默）；② `6–20` / `6-20` / `Borg` 改后各只剩 E7 那一次显式否定；③ 5.3 正文里那句自我指控 `**行号口径错、引文控制者未核**` **0** 命中；④ 14 个新串各命中预期次数（`控制者错误 #140` 刻意 **2** 次：E1 的撤回格 + E2 的正文）。

#### 3.2 计划正文的新字节数/行数

| 口径 | 改前 | 改后 |
|---|---|---|
| 字节 | **151 467 B** | **159 408 B**（+7 941 B） |
| 行（`len(text.split("\r\n"))`，与派单的「938 行」同口径） | **938** | **939**（E8 多加了一个列表项） |
| 行（`splitlines()`） | 937 | 938 |
| 换行 | 纯 CRLF（937 个，裸 LF 0） | **纯 CRLF**（938 个，裸 LF **0**） |
| BOM | 无 | **无** |
| `git diff --stat` | — | **12 insertions / 11 deletions**（11 行整行替换 + 1 行新增，无 CRLF 抖动） |

⚠️ **派单只要求改「更正」列，我照做了**：P5-A10 那一行的**事实列**一个字没动，于是同一行里「事实」列仍写着「**行号口径错**，且『明写严格大于』的引文控制者未核」、「更正」列以「**撤回**」开头整格反驳它。**两格直接对打。**→ **顶回，见 §9 第 6 条。**

E2 恢复后的 5.3 正文（可核的原文引用，硬规矩 #78 的「按可 grep 的原文找」半句保留）：三处可 grep 的原文各点名——① 一行 dict 定义 `BODY_FAT_LIMIT = {Sex.MALE: 20.0, Sex.FEMALE: 28.0}`；② 唯一消费点 `body_fat_pct > limit`；③ **定义行上一行**那句逐字注释「体成分异常 C 的体脂率阈值（spec §6.3②）：男 > 20%、女 > 28%，**严格大于**。」。本轮已用 Grep 亲核这三处都在 `backend/app/domain/derive.py` 里逐字存在（定义行的**上一行**就是那句注释）。

### 4. F1-4（Important）硬规矩 #82 / #83 入账

#### 4.1 `progress.md` 追加前后的字节数/行数

脚本 `t5_probes/_fr1_ledger_append.py`，用 `LEDGER.open("a", encoding="utf-8", newline="")` 追加、内容自己写 `\r\n`。**没用编辑器工具打开过这个文件。**

| 口径 | 追加前 | 追加后 |
|---|---|---|
| 字节 | **336 427 B** | **346 910 B**（+10 483 B） |
| 行（`splitlines()`） | **2 153** | **2 214**（+61） |
| 行（`len(text.split("\r\n"))`） | 2 154 | 2 215（+61） |
| 换行 | 纯 CRLF（2 153 个，裸 LF 0） | **纯 CRLF**（2 214 个，裸 LF **0**） |
| BOM | 无 | **无** |

**最强的一道闸门**（写盘后）：`after_text == before_text + payload` **逐字相同**——即前 336 KB 一个字都没被碰过。这一条是冲着 Ruling 116 那次事故写的（IDE 把陈旧且截断的缓存写回磁盘、永久丢了约 107 KB）。另有 10 个必需串的**写盘前**闸门（追加是不可撤销的，故闸门必须在写之前跑）：
`**→ 补硬规矩 #82：探针「0 命中」时` / `**→ 补硬规矩 #83：变异取证与任何「改了又还原」的取证` / `#### 一、控制者错误 #140` / `恰好等长（都是 47 字符）` / `四步又在**同一秒**内完成` / `#### 三、控制者采纳实现者的两处签名扩参` / `第 **5**、**6** 次顶回成立` / 两个扩参后的签名字面 / `**905 stmts / Miss 0 / 262 branch / BrPart 0 / 100%**`，**各命中 1 次 ✓**。

#### 4.2 硬规矩 #83 的正文（逐字，即入账那一份）

> **→ 补硬规矩 #83：变异取证与任何「改了又还原」的取证，必须在跑测试前 `shutil.rmtree(__pycache__, ignore_errors=True)` 并设 `PYTHONDONTWRITEBYTECODE=1`；**等长改动 + 同一秒**会让 CPython 的 `(mtime 截断到秒, size)` 失效判据不触发，于是加载陈旧字节码、产出假红或假绿。**

**依据（5.5 变异 ④ 的实测经过，本轮又独立复核了那两个具体条件）**：那条变异打的是 `intensity.py` 里 `hr_zone` 的取整方向。四步是「量基线 → 打变异 → 跑红 → 还原再跑绿」，而**还原后重跑出现了假红**：文件 sha256 **已还原成功**（逐字节相同），pytest 却仍报变异行为。本轮用探针 `t5_probes/_fr1_probe_47chars.py` **自己又数了一遍**那两个条件（硬规矩 #82 的自证义务也用在自己的入账上，不照抄派单）：

```
命中 1 处：
  行 170: len=47  '    return int(low_bpm), int(-(-high_bpm // 1))'
  变异后: len=47  '    return int(-(-low_bpm // 1)), int(high_bpm)'
  等长? True   差 = 0
```

→ **「恰好等长（都是 47 字符）」坐实**；四步在同一秒内完成（脚本是一次进程内跑完的）。两个条件合起来让 `(mtime 截断到秒, size)` 二元组一字未变 → `.pyc` 被判定仍有效 → 加载的是**变异版字节码**。

**它为什么比一般的 flaky 更危险**（三条，都写进了账本）：

* **假红**会让人**怀疑一个正确的还原**：于是「再还原一次」「再跑一次」，  而真因（陈旧字节码）从来不在被怀疑的清单里；更坏的是有人为了让它变绿而**再改一次代码**，  于是工作树与 index 悄悄分叉。
* **假绿更坏**：它让人以为**一条守卫还在工作**。变异取证的全部价值就是「M1 必须红」，  一次假绿等于把「这条守卫有牙」这个结论建立在一个**没被真正执行过的文件**上——  那正是硬规矩 #50/#53 要挡的「尺子恒绿」。
* 触发条件是**两个都很常见的巧合**（等长改动、同一秒完成），不是罕见的时序竞争，  故**会复发**：任何「语义等价改写」型的变异（正是硬规矩 #65 的 M1 对照要求的形状）  **天然等长**。

**本轮的三次取证一律带了这两项**：`import types` 的纯净性探针（脚本里 `clean_pyc()` + 子进程 `env["PYTHONDONTWRITEBYTECODE"] = "1"`，且还原后打印 `[还原] sha256 相同 = True（31817 B）`）、以及两次全量跑（终端里 `$env:PYTHONDONTWRITEBYTECODE="1"` + `-p no:cacheprovider`）。

#### 4.3 硬规矩 #82 的正文（逐字）

> **→ 补硬规矩 #82：探针「0 命中」时，必须先用一个已知存在的串验证这条查询本身有效，才允许把「没查到」讲成「不存在」。**

**依据**：账本 Ruling 147 的 **P5-A13**（用一个自己没验证过的正则去数一个已经有字面断言的量，数出 3 而真值是 24）与本次的 **P5-A10** 是**同一根因的两次发作**，而硬规矩 #80 只覆盖了「已有字面断言」那一半——**「探针 0 命中」这一半它管不到**：0 命中看起来像「事实」，而它同样可能是「查询本身无效」。自证的办法只有一步：拿一个**已知存在**的串跑同一条查询，看它是否命中。→ **控制者错误 #140**，与 #80 同型第 **9** 次。

**本轮自己就用了一次**：§4.2 那个 47 字符的复核，就是拿「已知存在的那一行」去验证「len() 这把尺子」有效，然后才把它写进账本。

#### 4.4 同一节还记了什么

账本追加节的完整目录：一、控制者错误 #140（+ 硬规矩 #82）；二、硬规矩 #83（`.pyc` 陈旧失效）；三、**控制者采纳实现者的两处签名扩参（Plan 02 实现者第 5、6 次顶回成立）**——`apply_safety(pkg, inp, eq, *, template, exercises)` 与 `apply_overrides(pkg, records, *, exercises)`，两条的理由逐字入账（`TrainingPackage` 里没有 `addons` / `weekly_frequency`；`SUBSTITUTE_EXERCISE` 只换 ref 会留着旧动作的视频 URL，那是「一个看起来正常的谎」）；四、本轮另两条 Critical 裁定（F1-1 / F1-2）；五、本轮的验收数字。
⚠️ **本节由实现者按 fix round 1 派单代笔入账，Ruling 编号留给控制者结案时统一分配**（账本上一个号是 Ruling 147），故标题里没有自铸新号。

### 5. F1-5（Minor）4 条待清扫的落地位置

| # | 条目 | 落地位置（补丁脚本的哪一条） | 写进去的内容 |
|---|---|---|---|
| ① | P5-A2 的分布口径未说明 | **E3** → 计划正文 Task 5 节「⚠️ 预检更正」总表的 P5-A2 那一格（事实列） | 在 `{2: 24, 3: 42, 4: 64}` 后面补明：**这个分布是按 block 计数加权的、不是按模板计数**——按 `exercise_ref` 去重是 `{2: 12, 3: 14, 4: 16}` 共 **42** 个 ref，各乘以自己的 `sessions_per_week` 才得到 `{2: 24, 3: 42, 4: 64}` 共 **130** 个 block。（这三个数与 `test_every_block_appears_in_every_session_of_the_real_templates` 的 docstring 里已有的口径逐字一致） |
| ② | 简报 5.5 漏点 `_OWNED_MODULES` 与第二句 assert | **E4** → 5.5 节 Step 5 的第一个 `- [ ]`（公开面那一条） | 补明两处：**① `_OWNED_MODULES` 从 3 个模块扩到 7 个**（支 5 的穷尽判据只对**本包拥有**的模块成立，Task 5 新建的四个都是本包拥有的，不加进去就等于**放弃这四个模块的穷尽守卫**——谁往 `assembler.py` 加一个公有顶层定义而不重导出，全量测试照样绿）；**② 那句 `assert len(...) == 24` 其实是两句**（`assert len(_PRESCRIPTION_PUBLIC_BASELINE) == 43` 与 `assert len(set(names)) == 43`，后者钉「基线里没有重名」），**两句都要改**。并逐字标注「**实现者超出派单发现，控制者采纳**」 |
| ③ | 5.3 的 `Consumes` 漏列 `Template` / `ExerciseSpec` | **E5** → 5.3 节的 `**Consumes:**` 那一行 | 补上 Task 2 的 **`ExerciseSpec`** 与 Task 3 的 **`Template`**，并注明「`apply_safety` 的签名已扩参成 `(pkg, inp, eq, *, template, exercises)`，`Consumes` 要跟上」。⚠️ **同一节 `Produces` 的签名行也一并改了**（E10a / E10b），因为它**当时还是旧签名**、只补 `Consumes` 会让同一节自相矛盾 → 见 §9 第 4 条 |
| ④ | 带 `--cov` 与不带的 passed 数差 1 | **E6** → 5.5 节 Step 5 的「全量 `pytest -q` 的 passed 数自己数」那一条 | 补明口径：不带 `--cov` 是 `N passed`，带 `--cov=app.domain --cov-branch` 是 `N-1 passed, 1 skipped`；那 **1 个 skip** 是 `tests/pipeline/test_backfill.py` 里**既有**的墙钟断言，它按硬规矩 #42 在 `sys.gettrace()` 非空时**主动跳**，而 `pytest-cov` 正是靠 `sys.settrace()` 实现的；Task 5 落地时实测 **679** / **678 + 1 skipped**，两个数指同一套测试，**没有丢测试**（正是为了「免得下一个 Task 的实现者以为丢了一条测试」） |

### 6. 最终验收（全部实现者亲跑）

| 项 | 基线（`fc8f5a8`） | 本轮 | 判据 |
|---|---|---|---|
| `python -m pytest -q` | 672 passed | **679 passed**（+7） | 亲跑 `61.27s` |
| `… --cov=app.domain --cov-branch` | 671 passed, 1 skipped | **678 passed, 1 skipped** | 亲跑 `138.98s`；差的那 1 个 skip 见 §5 的 ④ |
| 覆盖率四格 | 888 stmts / Miss 0 / 260 branch / BrPart 0 / 100% | **905 / 0 / 262 / 0 / 100%** | `+17` stmts（只读映射 12 + 两个 `_RPE_*` 常量 + 值域拒绝 2 + 分桶累加 1）、`+2` branch（`rpe` 值域那个 `if` 的两条弧）。**spec §12 的硬要求仍满足** |
| 公开面 `__all__` | 43 | **43** | `_ReadOnlyVolumeBase` 是私有的（§1.5）；`_PRESCRIPTION_PUBLIC_BASELINE` 与它的两句 `assert … == 43` 一个字没动 |
| 扫描面 | 32 | **32** | domain **14** + pipeline **7** + db **11** |
| 禁区指纹 | `D2C8E539E2FA0029` / `3DE598AF38631209` / `822CB86A5E998301` | **三个逐字不变** | 探针 `t5_probes/_fr1_verify.py` 逐个重算 sha256[:16] |
| `backend/pe.db` | 不存在 | **不存在** | 同上 |
| `backend/data/seed/` | 0 文件 | **0 文件** | 同上 |
| `backend/data/` | — | **一个字节没动** | `git status --short` 里 `backend/data/` 零条目；模板 YAML 仍是 18 个 / 123 848 B |
| 控制者实算的算例 | 逐格命中 | **仍逐格命中** | `interval_run` 第 1 周 **38.4** / 第 4 周 **32.6**；`compound_circuit` **96.0** / **81.6**；`hr_zone(194.0, 60, 70) == (116, 136)`；`volume_factor` **0.8** / band **`'low'`** |

**四个新模块的 sha256[:16] 与体积**（`intensity.py` / `safety.py` / `override.py` 本轮**一个字没改**，故它们的 sha256 与 5.5 收尾时相同）：

| 模块 | 字节 | 行 | 换行 | sha256[:16] | import 面 | 违规 |
|---|---|---|---|---|---|---|
| `intensity.py` | 13 092 | 193 | 纯 LF | `9D8336D25A2DF196` | `[]`（一个都没有） | 无 |
| `assembler.py` | **43 779**（改前 31 817） | **689** | 纯 LF | **`D443187E541379CE`** | `collections` / `collections.abc` / `dataclasses` / `app.domain.indicators` / `.exercises` / `.intensity` / `.templates` | **无 `import math`、无 `import types`、无 `import json`** |
| `safety.py` | 24 266 | 407 | 纯 LF | `BC471A4B5161D10C` | `collections.abc` / `dataclasses` / `.assembler` / `.exercises` / `.templates` | 无 |
| `override.py` | 24 483 | 419 | 纯 LF | `1E2E088C886B4990` | `collections.abc` / `dataclasses` / `enum` / `.assembler` / `.exercises` | 无 |

⚠️ **`assembler.py` 里没有 `import types`、也没有 `import json`**：只读映射靠 `dict` 子类实现，JSON 化的**证据在测试侧**（`tests/` 不受 domain 的 allow-list 约束）。两份架构守卫（`test_domain_purity.py` 4 条 + `test_layering.py`）本轮全绿。

### 7. 两个 commit 的 sha

1. **`fe3a6df`** —— `fix: Plan02 Task5 fix round 1 的 F1-1/F1-2 —— weekly_volume_base 按单位分列 + rpe 值域改 0–10`（3 个文件：`assembler.py` + 两个测试文件；+481 / −29）
2. **`f9b6ed5`** —— `docs: Plan02 Task5 fix round 1 的 F1-3/F1-4/F1-5 —— 撤回 P5-A10（控制者错误 #140）+ 硬规矩 #82/#83 入账 + 计划正文 11 处更正`（计划正文 + 账本 + 补丁脚本 + 本轮 14 个取证脚本）

⚠️ **commit 2 被 `--amend` 过一次**（`8350d30` → `f9b6ed5`，**没 push**，故安全；两个 commit 的数目没变）：`_fr1_report_append.py` 自己在commit 2 之后又被改过（写盘前闸门从「恰好 N 次」放宽成「至少 N 次」——真闸门是 `after_text == before_text + payload` 那一句逐字对账，这一组只挡「漏写了一节」），故把它补进 commit 2 而不是留一个脏工作树。

`git add` 一律**按文件名逐个加**；两条 commit 信息都是 python 写 UTF-8 无 BOM 临时文件 + `git commit -F`（`t5_probes/_fr1_msg1.txt` / `_fr1_msg2.txt`，两份都入库）。

### 8. 我没按本派单做的地方（**7 处**，逐条）

1. **没有走派单 F1-1 的 fallback**（「若 `MappingProxyType` 序列化失败，就在快照里存 `dict`，只读性靠 frozen dataclass + 文档约定」）。实测两条备选都不成立（`collections.abc.Mapping` 的自定义子类同样不可 JSON 序列化），落的是第三个构造：屏蔽 8 个 mutator 的 `dict` 子类，**同时满足只读与 JSON 化**，故派单要求的测试③（`pytest.raises(TypeError)`）**成立了**、没被降级成「等价的不可变性守卫」。取证见 §1.4。
2. **`weekly_volume_base` 的实现口径与派单的字面表述不同**：派单写「所有 block 的 `base × sessions_per_week` 之和」，字面照做会把课数乘两遍（`RED-END-ABN-01` 得 `{"min": 192.0, "reps": 480.0}`）。我按派单**自己给出的分解**（`48.0 min + 120.0 reps`）实现，落的是「逐 `(session, block)` 累加 `base`」，与去重后的 `base × sessions_per_week` 之和在真仓 **18/18** 逐格相等（探针对拍）。见 §1.6。
3. **加了 `[0, 10]` 的运行时校验**（派单说「加或不加都可以」，我选了加，并配了派单要求的四值边界测试）。理由四条见 §2.3。
4. **计划正文多改了 3 处**（E9 / E10a / E10b），都不在派单 F1-5 的字面 4 条里：E9 是六步口径第 6 步的 `weekly_volume_base` 类型（原文写「`float`，`round(…, 1)`」，F1-1 落地后与代码矛盾，而 Task 6/8 的实现者读的就是它）；E10a / E10b 是 5.3 / 5.4 的 `Produces` 签名行（**当时还是旧签名**，只补 F1-5③ 的 `Consumes` 会让同一节自相矛盾）。见 §9 第 4、5 条。
5. **只读映射做成了私有**（`_ReadOnlyVolumeBase`），故 `__all__` 是 **43 → 43**而不是 44。派单的验收清单问「`__all__` 的大小（43 → ?）」，答案是 **43**；理由（支 5 的穷尽判据 + 派单没要求扩公开面）见 §1.5。
6. **入库范围比派单的字面清单大**：派单只点名「补丁脚本入库」（`_t5_fr1_plan_patch.py`），我把本轮 **14 个取证脚本 + 2 份 commit 信息 + 1 份扫描输出**也一并入库了（`t5_probes/_fr1_*`）。理由是账本对 `t5_probe{1,2,3,4}.py` 记的就是「四份全部入库」，`fr2_probes/` / `fr3_probes/` / `fr4_probes/` / `t3_probes/` / `t4_probes/` 也全部已入库。
7. **`task-5-report.md`（本文件）与 `task-5-brief.md` / `_mk_brief5.py` / `_t5_verify.py` / `t5_probes/_fr1_fix_sha.py` / `t5_probes/_fr1_fix_report_list.py` 至今未入库**（后两个就是改本条与改 commit 2 那三处 sha 的脚本自己——**入库它们就得再 amend 一次、sha 又变、报告又得改**，故刻意止步于此），本轮也没提交（不在派单 commit 2 的字面清单里，且上一轮同样没提交）。⚠️ 但 `task-1..4-report.md` 与 `task-1..4-brief.md` **全部已入库**，`.superpowers/**` 又是 `-text`（git 不做行尾转换）。按 Ruling 116 的立意（审计链入库以防数据丢失），**这 4 个文件是当前唯一的裸露面**（本文件此刻 ≈ 100 KB，只在磁盘上）。在此报出请控制者裁定。

### 9. 我认为本派单错了的地方（**顶回 6 处**，这是 Plan 02 实现者第 7–12 次顶回）

**① F1-1 的口径表述有歧义，字面照做会算错。**「值 = 该单位下所有 block 的 `base × sessions_per_week` 之和」——若「所有 block」指遍历每个 `(session, block)` 实例，`RED-END-ABN-01` 会得到 `{"min": 192.0, "reps": 480.0}`（课数乘了两遍），而派单**自己**把 `168.0` 分解成 `48.0 min + 120.0 reps`。两处对打，我按后者（分解）实现。**这不是派单的结论错，是表述漏了「去重」两个字。**建议正文写成「值 = 该单位下**每个不同 `exercise_ref`** 的 `base × sessions_per_week` 之和」。

**② F1-1 的决策树漏了一格，照它走会自相矛盾。**派单说「`types` 红 → 改用 `collections.abc.Mapping` 标注 + 返回一个不可变的构造」，又说「若 `MappingProxyType` 序列化失败 → 就在快照里存 `dict`（只读性靠 frozen dataclass + 文档约定）」。而 **`collections.abc.Mapping` 的自定义子类同样不可 JSON 序列化**（`json` 的默认类型表只认 `dict` 及其子类），故第一条备选走到头**还是**落到第二条，于是派单**同时**要求的测试③（`with pytest.raises(TypeError): snap["weekly_volume_base"]["min"] = 0`）**无法成立**——派单要求了一个它自己的决策树排除掉的结果。第三个构造（屏蔽 mutator 的 `dict` 子类）同时满足两条，故没走 fallback。

**③ F1-2 那条「不要顺手加校验」的禁令，前提不完整。**派单给的唯一门槛是「能不能证明它不会让真仓模板炸」（能，`rpe` 出现 0 次）。但它没提到 **`hr_zone` 已经在同一层校验 `hrmax_pct` 的值域**（`0 <= low <= high <= 100`），而改前 `_render` 的 docstring 恰恰用「值域的校验属于加载器」当不加的理由——**那句话与本仓已有的做法自相矛盾**。故「单一所有者」在这里不构成反对理由；不加才是不对称的那个选择。我加了。

**④ F1-5③ 的前提「签名已经扩参了」在计划正文里不成立。**计划 5.3 / 5.4 的 `Produces` 两行**当时仍是旧签名**（`apply_safety(pkg, inp, eq)` / `apply_overrides(pkg, records)`）——扩参只发生在**代码**里。只补 `Consumes` 会让同一节的 `Consumes` 说有 `Template` / `ExerciseSpec`、而 `Produces` 的签名里没有它们。故连 `Produces` 两行一起改了（E10a / E10b），并把「控制者第 5 / 6 次采纳」的理由写进那两行。

**⑤ F1-1 是 Critical 级裁定，但派单没要求同步计划正文——那会留下一处活的矛盾。**计划 5.2 六步口径的第 6 步逐字写着 `weekly_volume_base` = 「未乘个体系数、未乘 `week_deltas` 的周量总和（**`float`**，`round(…, 1)`）」。F1-1 落地后这一行与代码矛盾，而 **Task 6 的实现者要照它建 `prescription` 表、Task 8 的实现者要照它建读模型**。派单 F1-3/F1-5 已经让我改计划正文了，把这一处落下是漏项，故补成 E9。**建议：凡 Critical 级的口径裁定，派单应当同时点名计划正文的哪一行要跟着改**（本轮 F1-1 没有）。

**⑥ F1-3 只要求重写「更正」列，于是 P5-A10 那一行自己跟自己打。**改后同一行里：「事实」列仍写着「计划 5.3 写的是「`derive.py:68-69`」，**行号口径错**，且「明写严格大于」的引文控制者未核」、「更正」列以「**撤回**…原计划的行号 `:68-69` 与引文双双正确」开头。对照账本 Ruling 147 里 **P5-A13** 的写法（那条同样是控制者错误，它的**事实列**直接以「**控制者错误 #139**：…」开头、把错的结论放在事实列里讲清楚），**本仓的既有惯例是连事实列一起改**。我按派单字面只改了「更正」列，请控制者裁定要不要照 P5-A13 的体例把事实列也改掉。

**另有一处口径提醒（不算顶回）**：派单说计划正文是「151 467 B / **938 行**」。实测 `splitlines()` = **937**、`len(text.split("\r\n"))` = **938**，故派单用的是后一种口径（把结尾换行后的空位也算一行）。本轮报告一律**两个口径都给**，免得下一个人数出 937 以为丢了行。

### 10. 本轮的取证脚本清单（全部入库）

| 脚本 | 干什么 |
|---|---|
| `_t5_fr1_plan_patch.py` | **计划正文的 11 处替换**（E1–E10b），四道落盘闸门 |
| `t5_probes/_fr1_env_probe.py` | 14 个关键文件的字节数 / 行数 / 换行 / BOM 对账 |
| `t5_probes/_fr1_probe_types_json.py` | **三条实测**：`import types` 让守卫变红（含还原后 sha256 对账）/ `MappingProxyType` 不可 JSON 化 / `dict` 子类两条都过 |
| `t5_probes/_fr1_probe_ior.py` | 撞出 `|=` 与 `copy.copy` 两个口子 |
| `t5_probes/_fr1_probe_reduce.py` | `__reduce__` 一次修好 copy / deepcopy / pickle |
| `t5_probes/_fr1_recompute_volume_base.py` | **不 import 被测模块**，直接读 18 份 YAML 独立重算 `weekly_volume_base`，并对拍两种口径（18/18 相同） |
| `t5_probes/_fr1_probe_47chars.py` | 硬规矩 #82 的自证：自己数一遍「47 字符等长」 |
| `t5_probes/_fr1_scan_rpe.py` / `_fr1_scan_narrow.py` | F1-2 的全仓扫（含取证件）与收敛扫（只 `backend/` + `Document/`，自动判定是否否定句） |
| `t5_probes/_fr1_plan_lines.py` / `_fr1_plan_range.py` / `_fr1_ledger_tail.py` | **只读**地看计划正文与账本（不打开编辑器） |
| `t5_probes/_fr1_verify.py` | 实现者自验：公开面 / 扫描面 / 三个指纹 / 禁区 / 四个模块的 sha256 与 import 面 / F1-1 的新类型与字面值 / 12 与 15 键的 JSON 化 / F1-2 的六个值 / 两处签名 / 控制者的算例 |
| `t5_probes/_fr1_ledger_append.py` | **账本追加**（`open(..., "a", newline="")` + 写盘前闸门 + `after == before + payload` 逐字对账） |
| `t5_probes/_fr1_commit1.py` / `_fr1_commit2.py` / `_fr1_report_append.py` | 两个 commit 与本节追加 |

**下一步**：控制者复核本轮 → Task 5 结案 → 抽 Task 6 简报。
