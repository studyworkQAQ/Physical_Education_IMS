# Task 3 实现者报告 — 18 套模板 YAML + `prescription_template` 表 + 加载器

> **状态：完成。** 一个 commit（代码 + spec + 本报告 + 取证脚本同笔入库），未 push。
> **本文件是新文件**（Task 3 之前不存在），故首次落盘不需要字节备份；若后续追加，先按硬规矩 #68 备份。
> 行号一律 shell 口径（python `read_bytes()` 数 LF），字节数一律 `read_bytes()`，绑定 commit 见各节。

---

## 0. 环境与基线复现（硬规矩 #72/#73）

**依赖冒烟（开工第一件事，`t3_probes/` 之外直接跑的 `python -c`）**

```
$ cd backend; python -c "import sys,sqlalchemy,pandas,numpy,yaml;print(...)"
3.11.1 2.1.3 3.0.6 2.4.6 6.0.3
```

Python **3.11.1** / SQLAlchemy **2.1.3** / pandas **3.0.6** / numpy **2.4.6** / PyYAML **6.0.3**，
与派单 §0 逐项相符。**没有撞上 `_cache_key_cy` 的 DLL 拦截**（Ruling 121 那个形态本轮未复现），
故不需要停下报告。无 venv，装在 `C:\Python\Lib\site-packages`。
⚠️ 本轮新用到的一个间接依赖：**coverage 7.16.2**（`t3_probes/p07_stmt_breakdown.py` 用它的
`coverage.parser.PythonParser.parse_source()` 取「coverage 认为哪些行是语句」，见 §7）。
Task 2 的报告没记 coverage 的版本，本轮补上。

**基线核对**

| 项 | 派单声称 | 我实测 | |
|---|---|---|---|
| HEAD | `ddccba8` | `ddccba80b423bac69a2e5146db0d7f1333d7ff60` | ✓ |
| 分支 | `feature/plan-02-prescription-engine` | 同 | ✓ |
| 工作树 | 干净 | `git status --short` 空 | ✓ |
| `git diff --name-only c29bc69 ddccba8 -- backend` | 应为空 | **空** | ✓ |
| `pytest -q` | 531 passed | **531 passed in 63.50s** | ✓ |
| `--cov=app.domain --cov-branch` | 441 stmts / Miss 0 / 120 branch / BrPart 0 / 100%、530 passed + 1 skipped | **逐格相同**（138.42s） | ✓ |
| `Base.metadata.tables` | 15 张 | **15** | ✓ |
| `SCANNED_DIRS` | pipeline 7 + db 11 + domain 9 = 27 | **7 / 11 / 9 = 27** | ✓ |
| `.gitattributes` 规则 | `:13` csv / `:14` yaml / `:15` md / `:38` `.superpowers/** -text` | **逐条相符**（改前 38 行） | ✓ |
| `git check-attr` 改前 | `prescription/RED-END-ABN-01.yaml` → `text: unspecified / eol: unspecified` | **逐字相符** | ✓ |
| `Layer` 成员 | RED/YELLOW/GREEN/INSUFFICIENT | **相符** | ✓ |
| `ITEM_BUCKET` 非 None 值 | 三个桶名，最长 17 | **相符** | ✓ |
| 动作库 | 23 个 ref，无 `energy_expenditure_plus_5min_hiit` | **相符** | ✓ |

---

## 1. 交付清单

### 1.1 新建（20 个文件）

| 路径 | 内容 |
|---|---|
| `backend/data/prescription/RED-END-ABN-01.yaml` … `GRN-SPD-NOR-18.yaml` | **18 个**模板，合计 **123 848 B**，全部 **CRLF = 0**，逐个 sha256[:16] 见 §5 |
| `.superpowers/sdd/2026-10-06-实施计划02-智能处方引擎/task-3-report.md` | 本文件 |
| `.superpowers/…/t3_probes/*.py`（9 个）+ `mutation_log.txt` | 取证脚本与变异日志（命名避开 Task 1 的 `fr{N}_probes` 与 Task 2 的 `t2fr3_probes`） |

### 1.2 修改（12 个文件）

| 路径 | 改后 bytes / 行 / CRLF / sha16(归一化) | 改了什么 |
|---|---|---|
| `.gitattributes` | 4 385 B / 50 行 / CRLF 50 / `FC68C1577BD58CA4` | **+1 条规则** `backend/data/**/*.yaml text eol=lf`（P3-D2）+ 11 行注释 |
| `Document/…设计spec.md` | 98 755 B / 1 013 行 / CRLF 1013 / `DACB9460C194D19D` | §14 **+2 行**（#29 / #31）+ 表后 1 段编号说明；§7.2 **+6 条勘误** |
| `backend/app/domain/prescription/templates.py` | 20 388 B / 334 行 / CRLF 334 / `22FC9C08B482367D` | 从 2 stmts 的空壳变成 **12 个公有顶层定义**（见 §3） |
| `backend/app/domain/prescription/__init__.py` | 3 901 B / 83 行 / CRLF 83 / `999D8EEA4455BC3C` | 公开面 **7 → 20** 个名字 |
| `backend/app/domain/prescription/exercises.py` | 16 915 B / 254 行 / `3E13D9E322C9D9A4` | **一个字没改**（`t3_probes/p10_change_surface.py` 逐字节核过，sha 与基线相同） |
| `backend/app/refdata_prescription.py` | 66 752 B / 1 229 行 / CRLF 1229 / `9955057A37880178` | +30 个顶层定义（模板加载器 + `sync_templates`）；既有 12 个 **AST 逐字不变** |
| `backend/app/db/models/prescription.py` | 22 453 B / 299 行 / CRLF 299 / `E3342B342AB7763B` | +`PrescriptionTemplate`（第 **16** 张表）；`Exercise` 类 **AST 逐字不变**；docstring 三处更新 |
| `backend/app/db/models/__init__.py` | 7 249 B / 109 行 / `C0C2138C8830143A` | **只改注释**（剥模块 docstring 后 AST 相同，已核）；`__all__` 未动（Ruling 97） |
| `backend/data/exercises.yaml` | 22 739 B / 364 行 / **CRLF 0** / `3DE598AF38631209` | 23 → **24** 个键（+`energy_expenditure_plus_5min_hiit`）；头注释 3 段更新 |
| `backend/data/exercise_equivalence.yaml` | 8 245 B / 130 行 / CRLF 0 / `822CB86A5E998301` | **一个字没改**（逐字节核过；数据部分与 `version` 全部不变） |
| `backend/tests/domain/test_prescription_templates.py` | 78 719 B / 1 252 行 / CRLF 1252 / `592602ACABB99761` | 4 条 → **42 条**（+38） |
| `backend/tests/test_refdata_prescription.py` | 79 028 B / 1 290 行 / CRLF 1290 / `7705A7032834BEFA` | 45 条 → **57 条**（+12）；`EXERCISES_FINGERPRINT` 与公开面基线更新 |
| `backend/tests/db/test_models.py` | 46 365 B / 774 行 / CRLF 774 / `BDA6F1FF7912933D` | `== 15` → `== 16`（3 处真断言 + 3 处散文）、函数名、`expected` 集合、列数 11 → 15 |
| `backend/tests/seed/test_generate.py` | 68 562 B / 1 209 行 / CRLF 1209 / `CCAF7CF6B05AEED9` | `REFERENCE_TABLES` **两处**同步 |

⚠️ 上表的 `bytes / 行 / CRLF` 三列都是**工作树**值，`sha16` 是**归一化（CRLF→LF）后**的值。
派单 §5 那张表把两种口径混在一行而没标注，我实测确认了它的换算关系（见 §9 CE-6）。

**没有新建任何 `.py` 生产模块**（`SCANNED_DIRS` 三个数一个未变，27 = 7+11+9），
也**没有**新建 `tests/domain/test_prescription_exercises.py`（见 §10 未尽事项 ①）。
**`app/seed/` 一个字没改**、**没有**新建 `app/seed/prescription.py`（P3-A1，Critical）。

---

## 2. TDD 的红 → 绿链（四次实跑，逐次留证）

派单要求「报告里要贴红的那一次输出」。四次都贴。

### 2.1 红 1 —— 只有测试、完全没有生产码

```
$ cd backend; python -m pytest -q tests/domain/test_prescription_templates.py tests/test_refdata_prescription.py
ERROR collecting tests/domain/test_prescription_templates.py
tests\domain\test_prescription_templates.py:84: in <module>
    from app.db.models.prescription import PrescriptionTemplate
E   ImportError: cannot import name 'PrescriptionTemplate' from 'app.db.models.prescription'
ERROR collecting tests/test_refdata_prescription.py
tests\test_refdata_prescription.py:68: in <module>
    from app.db.models.prescription import Exercise, PrescriptionTemplate
E   ImportError: cannot import name 'PrescriptionTemplate' from ...
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!
2 errors in 0.48s          （退出码 2）
```

**为什么是收集期 ImportError 而不是断言失败**：新测试的 import 面里有三个还不存在的名字
（`PrescriptionTemplate` / `templates.Template` 等）。这与 Task 2 报告的「红 1」同形态
（那一次也是收集期炸）。它证明的是「测试引用的东西确实还不存在」，不是「断言写错了」。

### 2.2 红 2 —— 生产码齐了、18 个 YAML 还没有

```
$ python -m pytest -q tests/domain/test_prescription_templates.py -k "loader or round_trips or pending or constructible or is_reachable or layers or weakness or body_comp or intensity_types"
>           raise FileNotFoundError(f"处方模板目录缺失: {folder}")
E           FileNotFoundError: 处方模板目录缺失: C:\...\backend\data\prescription
1 failed, 21 passed, 20 deselected in 0.77s          （退出码 1）
```

**这 21 passed 里含加载器的全部 10 格拒绝用例 + 已知 GREEN 的往返对照**——即加载器在
「18 份真文件还不存在」的时候就已经被合成 YAML 验完了。唯一红的那条
（`test_intensity_types_and_addon_triggers_are_pinned_verbatim`）红在「词表里的取值必须
在真数据上出现过」那一支，正是它该红的地方。

### 2.3 红 3 —— 18 个 YAML 落地了、指纹常量还是哨兵 `__PENDING__`

```
$ python -m pytest -q tests/domain/test_prescription_templates.py
E   AssertionError: 模板 GRN-END-ABN-13 被改动了：GRN-END-ABN-13.yaml 的 sha256 前 16 位是
    89842C7A0D8A6EA0，钉住的是 __PENDING__。…
      - __PENDING__
      + 89842C7A0D8A6EA0
1 failed, 41 passed in 0.82s          （退出码 1）
```

**41 passed 是这次最有信息量的数**：18 份 YAML 一落地，全矩阵 / 3 套不可达 / 红 4 黄 3 绿 2 /
`week_deltas` 长度与减量形状 / **sessions 总数 54** / `day` 连续 / addons 层归属 /
`exercise_ref` 存在性 / `impact_level` 与动作库一致 / addon module 存在性 / 三个无 CHECK 列的
列宽 / 工作树纯 LF —— **一次全绿**。只有指纹是哨兵，故只有它红。

### 2.4 绿

```
$ python -m pytest -q                                              → 581 passed in 58.76s
$ python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing
Name                                   Stmts   Miss Branch BrPart  Cover   Missing
app\domain\prescription\__init__.py        4      0      0      0   100%
app\domain\prescription\exercises.py      38      0      6      0   100%
app\domain\prescription\templates.py      58      0      0      0   100%
TOTAL                                    499      0    120      0   100%
580 passed, 1 skipped in 137.49s
```

**531 → 581 passed（+50）**：`test_prescription_templates.py` 4 → **42**（+38）、
`test_refdata_prescription.py` 45 → **57**（+12）。条数由 `pytest --collect-only -q` 实数
（`t3_probes/p11_sizes.py`）。skip 仍是 `test_backfill.py` 那条 trace-hook 自觉跳过，与基线同一个。

**新增的 50 条**（派单说「约 10 条」，实际远超，逐条列在 §3.3 与 §4；超出部分逐条给了理由）。

---

## 3. 交付内容的设计决定

### 3.1 `template_id` 的 18 个全清单（派单要求一行列出）

```
RED-END-ABN-01  RED-END-NOR-02  RED-STR-ABN-03  RED-STR-NOR-04  RED-SPD-ABN-05  RED-SPD-NOR-06
YEL-END-ABN-07  YEL-END-NOR-08  YEL-STR-ABN-09  YEL-STR-NOR-10  YEL-SPD-ABN-11  YEL-SPD-NOR-12
GRN-END-ABN-13* GRN-END-NOR-14  GRN-STR-ABN-15* GRN-STR-NOR-16  GRN-SPD-ABN-17* GRN-SPD-NOR-18
```
（`*` = `reachable: false` 的 3 套预留位）

**格式**照 spec §7.2 `:454` 的骨架首行 `RED-END-ABN-01`：`<层3>-<桶3>-<体成分3>-<序号2>`、
大写、连字符、**14 字符**（18 个全等长，故 `template_ref String(32)` 余量 18）。

**三字母缩写**（spec 只给了 `END` 与 `ABN`，其余由我定，已写进 18 份 YAML 的头注释与
spec §7.2 勘误 ⑥）：

| 维度 | 缩写 |
|---|---|
| 层 | `RED` / `YEL` / `GRN` |
| 主导短板 | `END`（spec 给） / `STR` / `SPD` |
| 体成分 | `ABN`（spec 给） / `NOR` |

**序号 = 全局序号 01–18**，枚举序 = 层（红→黄→绿）× 短板（耐力→力量→速度柔韧）×
体成分（**异常→正常**）。

⚠️ **「异常在前」这个选择是被 spec 逼出来的、不是我随手定的**：spec 只给了一个 id
（`RED-END-ABN-01`）。任何「正常在前」的定序都会让 `RED-END-ABN` 变成 `-02`，即与 spec 的
字面冲突；而派单明令「照 spec §7.2 `:454` 的格式」。全局唯一序号（而不是每层各 01–06）
是为了让专家可以只说号不说维度。已写进 spec §7.2 勘误 ⑥。

### 3.2 3 套 unreachable **要有完整 `sessions`**（我的决定 + 理由）

**决定：要，与其余 15 套完全同形，只有 `reachable` 一个字段不同。**
于是 `sessions` 总数 = **54**（`6×4 + 6×3 + 6×2`），已写成断言
（`test_sessions_total_is_fifty_four`，并按层分解钉住 `{"red": 24, "yellow": 18, "green": 12}`）。

**我复核过控制者给的 54**（派单 §2 要求）：逐套实数相加一致，`per_layer` 分解也一致。✓

三条理由（也逐字写进了那 3 份 YAML 的头注释与那条测试的 docstring）：

1. spec §7.1 `:447` 的②逐字是「分层规则未来若调整…**模板位已就绪**」——「就绪」意味着
   内容齐全，空壳不是就绪。派单说这个前提「控制者没法替你定」，**而 spec 已经给了答案**
   （见 §9 CE-3）。
2. `:447` 的①是「维持指导文件『18 套』的字面完整性，**专家评审时无需解释为何只有 15 套**」
   ——专家要能审的是一套真模板。
3. **空壳会迫使加载器开一条豁免分支**，于是 18 套里有 3 套走另一条校验路径，而那条路径
   **永远不被真数据走过**——正是 Review Focus 第 1 条要消灭的静默失效。同形则只有一条路径。

副作用：`GRN-*-ABN-*` 三份的 `addons` 也是 `[]`（绿层无 addon，见 §3.4），这在语义上有点怪
（体成分异常却没有能量消耗模块），但它们 `reachable: false`、不参与匹配，故不产生行为。
已在 YAML 注释里点明。

### 3.3 每格 blocks 的出处（**没有一个运动生理学参数是编的**）

`focus` 一律 = 桶名（耐力 / 力量 / 速度柔韧），出自骨架 `:468` 的 `focus: 耐力`；
同一套模板每一天 `focus` 与 `blocks` 都相同——**指导文件按「层 × 短板」给参数、没有按
周内第几天给**，分化到「周一练什么」需要专家给参数，已并入 spec §14 #29 的审校范围。

`structure` 只用骨架 `:473` 与 `:477` 那两个**字面**字典，按「时间型 / 次数型」二选一：
时间型 `{sets: 4, work_min: 3, rest_min: 2}`（跑、拉伸、球类、越野）、
次数型 `{rounds: 3, reps: 10}`（循环、自重、弹力带、药球、跳跃）。规则写进了每份 YAML。

| 层 × 短板 | blocks（ref / impact / intensity） | 出处 |
|---|---|---|
| red × endurance | `interval_run` high `hrmax_pct 60-70`；`compound_circuit` medium `onerm_pct 70` | 骨架 `:470-477` **逐字** |
| red × strength | `compound_circuit` medium `onerm_pct 70`；`medicine_ball_core` medium `onerm_pct 70`；`plyometric_jump` high `none` | `:487`「70% 1RM 复合循环」+ `exercises.yaml` 补项 3/4 的层归属注释 |
| red × speed_flexibility | `sprint_50m_intervals` high `hrmax_pct 60-70`；`shuttle_run` high `hrmax_pct 60-70`；`dynamic_stretching` low `none` | **借用**红层耐力的 60–70%（§14 #31） |
| yellow × endurance | `steady_run` medium `none`；`step_training` medium `none` | `:487`「持续跑+台阶训练」 |
| yellow × strength | `bodyweight_resistance` low `none`；`band_resistance` low `none` | `:487`「自重+弹力带抗阻」 |
| yellow × speed_flexibility | `shuttle_run` high `none`；`sit_and_reach_drill` low `none`；`pnf_stretching` low `none` | **空洞**（§14 #31） |
| green × endurance | `orienteering` medium `none`；`interest_ball_games` medium `none` | `:487` 绿层那一段 |
| green × strength | `functional_training` low `none`；`challenge_task` medium `none` | 同上 |
| green × speed_flexibility | `interest_ball_games` medium `none`；`agility_ladder` medium `none` | 同上 + `exercises.yaml` 补项 5 |

**`intensity: {type: none}` 覆盖 12 套（黄 6 + 绿 6）+ 红层的 2 个 block**。理由：`:487` 只给了
**红层**两个数（60–70% HRmax、70% 1RM），黄层与绿层一个数都没有。`none` 是「指导文件未给」
的**显式**取值而不是留空（留空分不清「不需要」与「忘了填」，与 `exercises.yaml` 的
`equipment: none` 同一条理由）。红层力量的 `plyometric_jump` 也是 `none`：1RM 是杠铃类动作的
概念，跳跃类没有可加载的 1RM。→ **这是我发现的第二个空洞**（简报只点了 speed_flexibility
那一个），已写进 spec §7.2 勘误 ②，并并入 §14 #29 的审校范围（不另占编号，理由见勘误 ②）。

**24 个 ref 里今天没有模板引用的是 3 个**：`hiit`、`brisk_walking`、`stationary_cycling`。
后两个是等价表的 low 落点（`exercises.yaml` 补项 1–2 的注释就是这么写的），本就不该出现在
模板里；`hiit` 是**新情况**（P3-A4 把黄层 addon 拆给了新 ref），见 §10 关切 ②。

### 3.4 addons 的层归属

| 层 | addons | 出处 |
|---|---|---|
| red（6 套） | `body_fat_over → energy_expenditure_plus_10pct`；`muscle_low → resistance_priority` | 骨架 `:480-484` **逐字** |
| yellow（6 套） | `body_fat_over → energy_expenditure_plus_5min_hiit`；`muscle_low → resistance_priority` | `:487`「体脂偏高附加 5min HIIT」+ `muscle_low` 照红层 |
| green（6 套） | `[]` | **指导文件没提**（简报 Step 2-5 的裁定） |

`muscle_low → resistance_priority` 黄层照抄红层的依据：骨架 `:483-484` 没给层限定，且
spec §7.4 `:509`「肌肉量 < P10 → 同上，并提高抗阻模块比重」也没给层限定。

**addon 与 `body_comp` 维度无关**：同层 6 套的 addons 完全相同，包括 `*-NOR-*` 那 9 套。
理由：addon 是**运行期条件式**的（Task 7 按学生当下的体测值判定），声明它不等于它会触发；
而模板的 `body_comp` 是**分层时点**的粗档。把两者绑起来会让一个「分层时体成分正常、
期中体脂超标」的学生拿不到能量消耗模块。写进了 `Addon` 的 docstring 与那条测试。

合计 24 条 addon（红 6×2 + 黄 6×2 + 绿 0），已写成空转守卫
（`assert sum(len(t.addons) …) == 24`）——否则「addons 恰好全空」会让存在性那条恒绿。

### 3.5 审校块（用户已裁定）

18 套全部 `status: approved` / `reviewer: 原型自审（占位）` / `reviewed_at: "2026-10-06"`
（**固定字面量**，不是 `date.today()`）/ `version: "1.0"`。已登记进 spec §14 **#29**。

⚠️ `version` 与 `reviewed_at` **必须加引号**：不加引号时 PyYAML 把 `1.0` 解析成 `float`
（于是 `1.10` 静默变成 `1.1`）、把 `2026-10-06` 解析成 `datetime.date`。前者让版本号变形，
后者会让 domain 侧字段类型随引号漂（`app/domain/` 的 allow-list 不放行 `datetime`）。
口径与 `exercise_equivalence.yaml` 的 `version: "1.0"` 一致。→ spec §7.2 勘误 ⑤。

⚠️ **`Template.reviewed_at` 的类型是 `str | None` 而不是 `datetime.date`**，因为
`ALLOWED_MODULES` 实测只有 6 个串（`dataclasses` / `enum` / `collections` /
`collections.abc` / `numpy` / `typing`）+ `app.domain` 前缀，**不含 `datetime`**
（`t3_probes/p02_probe_domain.py` 实读 `_is_allowed` 与 `ALLOWED_MODULES`）。为了一个日期
字段放宽那道架构守卫，代价是 domain 从此可以读时钟（GC #1 点名要挡 `date.today()`）。
`str → date` 的转换只有一处，在落库边界 `sync_templates`。

### 3.6 `Layer` 用**绝对**导入（P3-D4 要我选并说明理由）

`from app.domain.stratify import Layer`（**不是** `from ..stratify import Layer`）。三条理由：

1. **与 Task 2 的选择一致**：`exercises.py` 写的是 `from app.domain.indicators import ITEM_BUCKET`，
   既有 4 个 domain 模块跨模块引用一律绝对串。派单要求「不要出现一半绝对一半相对」。
2. **零处散文因此变假**：实测全仓 15 条相对导入**全部 `level == 1`**、分布 `{1: 15}`
   （`t3_probes/p02_probe_domain.py`）。选相对导入会让 `tests/architecture/test_domain_purity.py:467`
   与 `test_layering.py:162-164` 那两段「`level == 2` 在真仓里**今天仍不存在**」当场变假，
   而那两个文件**不在本 Task 的授权改动面里**（带进 Task 3 的清单 ⑩ 也是这么说的）。
3. `templates.py` 里保留的那一句 `from .exercises import ImpactLevel` 是 Task 2 就有的
   `level == 1` 包内导入，我没动它；故相对导入总数仍是 **15**、分布仍是 `{1: 15}`，
   `test_domain_purity.py` 与 `test_layering.py` 一个字都不用改（实测两者全绿）。

---

## 4. 新增测试逐条清单（50 条）

### 4.1 `tests/domain/test_prescription_templates.py`（+38：4 → 42）

**维度词表与值对象（domain 侧，不读盘）**

| # | 测试 | 守什么 |
|---|---|---|
| 1 | `test_templates_module_still_reexports_layer` | `templates.Layer is stratify.Layer`（`is` 不是 `==`）；`Layer` 四个成员的**声明序**；18 套里只出现前三个 |
| 2 | `test_template_layers_are_the_first_three_layer_members` | `TEMPLATE_LAYERS` = 三个，**排除** `INSUFFICIENT` |
| 3 | `test_weakness_bucket_values_are_the_three_item_bucket_names` | 取值与声明序字面钉住 + **跨所有者对账** `== set(ITEM_BUCKET.values()) - {None}`（简报 Produces 逐字要求） |
| 4 | `test_body_comp_state_and_review_status_values_match_spec_7_2_verbatim` | 两个二元词表的取值与声明序（骨架 `:458` / `:461`）+ 词表外值当场炸 |
| 5 | `test_intensity_types_and_addon_triggers_are_pinned_verbatim` | 两张词表字面钉住 + 18 套里实际用到的取值都落在词表内 |
| 6 | `test_is_reachable_is_false_for_exactly_the_green_abnormal_cells` | 6 个「层 × 体成分」格里**恰好一格**为假（真值表穷举，不是抽查） |
| 7 | `test_a_pending_template_is_constructible_so_task_4_has_something_to_reject` | **P3-A8 划归 Task 3 的那一半**：`Template` 构造期不校验 `review_status`，`pending` 可构造；顺带钉 `frozen=True`（Task 8 的前提） |

**18 套模板的内容（实际侧一律来自磁盘）**

| # | 测试 | 守什么 |
|---|---|---|
| 8 | `test_exactly_eighteen_templates_cover_the_full_matrix` | 键集 = 字面写死的 18 个 id；格子集合 = 3×3×2 全笛卡尔积（字面字符串三元组构造）；**且 `len(cells) == len(loaded)`**（抓「两套占同一格」） |
| 9 | `test_three_green_abnormal_templates_are_marked_unreachable` | 字面写死的 3 个 id：`reachable is False`、层是 green、体成分是 abnormal、`is_reachable` 为假、**且结构与其余 15 套同形**（§3.2 的③） |
| 10 | `test_the_other_fifteen_are_reachable` | 其余 15 个（用集合差算，与 #9 互补穷尽 18） |
| 11 | `test_weekly_frequency_follows_the_guidance_document` | 支 1 钉字面量 `{red:4, yellow:3, green:2}`（否则两侧同源）；支 2 逐套核对 + `len(sessions) == weekly_frequency` |
| 12 | `test_week_deltas_length_equals_microcycle_weeks` | `microcycle_weeks == 4`、长度相等、`== (1.00,1.05,1.10,0.85)`、末项 < 1.0、其余 ≥ 1.0 |
| 13 | `test_sessions_total_is_fifty_four` | **P3-C2 的强不变量**：按层分解 `{red:24, yellow:18, green:12}` + 合计 54 |
| 14 | `test_sessions_are_numbered_from_one_and_carry_at_least_one_block` | `day` == `1..N` 连续、`focus` 非空、每课 ≥1 block、`structure` 是 `mappingproxy` 且写它会 `TypeError` |
| 15 | `test_addons_follow_the_guidance_document` | 逐套核对三层的 addons（字面写死） |
| 16 | `test_every_template_id_matches_its_filename` | 文件名（去 `.yaml`）== `template_id`，且目录里**恰好** 18 个 `.yaml` |
| 17 | `test_all_eighteen_share_the_same_review_and_version_block` | 18 套的 `version` / `review_status` / `reviewer` / `reviewed_at` 逐字相同，且 `reviewed_at` 是 **str**（钉住 §3.5 那个 allow-list 决定） |

**跨文件不变量**

| # | 测试 | 守什么 |
|---|---|---|
| 18 | `test_every_exercise_ref_exists_in_the_exercise_library` | 简报 Step 1 点名的那条（Review Focus 第 1 条第 3 种坏形状）。两侧不同源：实际侧来自模板 YAML、期望侧来自 `exercises.yaml` |
| 19 | `test_every_block_impact_level_matches_the_exercise_library` | **P2-B2 的漂移守卫**（带出全部漂移的四元组诊断） |
| 20 | `test_every_addon_module_exists_in_the_exercise_library` | #18 只遍历 `sessions`、**看不见 addons**，而 spec §7.4 `:510` 恰恰走 addons 那一路；含空转守卫（24 条） |

**指纹与行尾**

| # | 测试 | 守什么 |
|---|---|---|
| 21 | `test_template_yaml_fingerprints_are_pinned` | **逐个文件**钉 18 个 sha256[:16]（见 §5 的方案选择理由） |
| 22 | `test_every_template_yaml_is_lf_only_in_the_worktree` | **P3-D2 的收口**：18 份工作树字节 CRLF == 0。⚠️ 指纹测试先归一化、**守不住这件事**，故必须另立一条 |

**列宽（P3-A5）**

| # | 测试 | 守什么 |
|---|---|---|
| 23 | `test_template_string_column_widths_fit_the_yaml_values` | `template_ref` / `version` / `reviewer` 三个**没有 CHECK、故不被 `test_models.py` 那道遍历测试覆盖**的列；第三支字面钉住实测最长值 `{14, 3, 8}`（否则「列宽与实际值一起缩水」时恒真） |

**加载器的响亮失败（Review Focus 第 1 条）**

| # | 测试 | 守什么 |
|---|---|---|
| 24–33 | `test_loader_rejects_a_broken_template`（**参数化 10 格**） | 简报 `:281` 的 6 种 + **P3-C3 的 2 种嵌套块缺失** + `impact_level` 漂移 + `reachable` 与维度矛盾。每格三支：`needle in message`、`path.name in message`、**`"第 " in message`**（行号是 Review Focus 第 1 条的原文要求） |
| 34 | `test_a_wellformed_synthetic_template_round_trips` | **已知 GREEN 的对照**（硬规矩 #53）：少了它，「把校验改成一律 raise」能让上面 10 格全绿。同时逐字段钉住**摊平**结果（`review` → 3 个字段、`progression` → `week_deltas`）与 int→float 收敛 |
| 35 | `test_loader_preserves_a_pending_review_status_verbatim` | **变异 ① 的目标判据**（P3-A7 的改写版），用 `tmp_path` 合成 YAML，不动那 18 份 |
| 36 | `test_loader_rejects_a_second_template_reusing_an_id` | 两个文件同 id 必须响亮失败（`exercises.yaml` 那个「后者覆盖前者」失效形态的模板侧版本），且报错点名**是哪一个文件重复了** |
| 37 | `test_loader_reports_the_file_when_a_template_is_not_valid_yaml` | 语法错也要点名文件（`YAMLError` 不是 `ValueError` 子类、且 mark 里没有文件名，故包一层） |
| 38 | `test_loader_reports_a_missing_or_empty_template_directory` | 目录不存在 → `FileNotFoundError`；空目录 → `ValueError`。**两者刻意不同异常类型**（部署问题 vs 内容问题） |

**改了的既有 4 条**：`test_templates_module_still_reexports_impact_level` 的支 1 期望值从
`["ImpactLevel"]` 扩到 **14 个名字**（守卫本身**没删**，派单明令）；它的 docstring 里
「`templates.py` 今天只有 **2** 条语句」「**唯一的导入方**是本文件顶部那两句」两处**已过期**，
改成「Task 2 时点的历史值」并写明 Task 3 之后为什么那条脆弱性自然消失、以及**为什么守卫
仍然要留**（它守的从来不是覆盖率，是 re-export 与 `__all__` 本身）。另三条一个字没改。

### 4.2 `tests/test_refdata_prescription.py`（+12：45 → 57，新「闸 5」）

| # | 测试 | 守什么 |
|---|---|---|
| 1 | `test_load_templates_is_read_only_and_cached` | `templates()` 是单例、返回 `MappingProxyType`、写它 `TypeError`；`load_templates()` **不**缓存（与 `load_exercises`/`load_standard` 同口径，P2-A9） |
| 2 | `test_sync_templates_projects_every_template_and_is_idempotent` | 返回 **== 18**（⚠️ 精确值，不是下界：18 是**封闭**矩阵，与 `exercise` 那条 `>= 20` 的理由相反，已在 docstring 里说明）；逐列对账含 `reviewed_at` 的 `str → date` 转换；重跑不翻倍 |
| 3 | `test_sync_templates_updates_a_changed_field_in_place` | upsert 的 PATCH 语义：改坏一行后重跑必须**就地更新**（`review_status`/`reviewer`/`reviewed_at`/`reachable` 四列一起验） |
| 4 | `test_prescription_template_ref_is_unique_at_the_db_level` | `template_ref` 的 UNIQUE（Task 9 的 `prescription.template_id` 要引它） |
| 5–10 | `test_prescription_template_check_constraints_reject_unknown_values`（**参数化 6 格**） | 四个 `_in_domain` CHECK 真的建进 DDL 并生效。**第一格 `("layer","insufficient_data")` 是主角**（简报 Step 6 括号注释逐字要求「不含 `insufficient_data`」）；`("weakness","bmi")` 那格钉 P2-A4 |
| 11 | `test_prescription_template_vocabulary_agrees_with_the_domain_enums` | ORM 四个类常量 ↔ domain 枚举/词表**两份对账**（`LAYERS` 对的是 `TEMPLATE_LAYERS` 三个、**不是** `Layer` 四个）+ 三个字面值 |
| 12 | `test_prescription_template_is_not_in_the_models_public_namespace` | **Ruling 97 / 带进 Task 3 的清单 ⑨**：新表不进 `models` 公有导入面。⚠️ 它是那条 33 名基线守卫的**补充**不是替代（那条被改坏时本条仍红） |

**改的既有部分**：`EXERCISES_FINGERPRINT`（见 §6）、`_PRESCRIPTION_PUBLIC_BASELINE` 与它的
六支（见 §8）、文件 docstring 的闸 4 描述（7 → 20 个名字）与「守不住什么」三条
（Task 2 写的「不守模板 ref 存在性 / 不守 impact_level 副本一致」两句现在**已过期**，
按硬规矩 #66 就地标注为历史并指向新守卫，而不是删掉）。

---

## 5. 指纹方案：**逐个文件钉**（简报 `:280` 把这个选择留给实现者）

```python
TEMPLATE_FINGERPRINTS = {
    "RED-END-ABN-01": "C0C61D2140A521D0",   # 6865 B
    "RED-END-NOR-02": "FE91666F74C08CAF",   # 6863 B
    "RED-STR-ABN-03": "8F4D51E3377FA814",   # 7872 B
    "RED-STR-NOR-04": "3E8C365CD0B4C133",   # 7870 B
    "RED-SPD-ABN-05": "8E396D8BF85B6DBD",   # 7930 B
    "RED-SPD-NOR-06": "0EDDE329A6CA61AE",   # 7928 B
    "YEL-END-ABN-07": "D301AE8D8D3D6B7E",   # 6480 B
    "YEL-END-NOR-08": "F08B64A00D974F18",   # 6478 B
    "YEL-STR-ABN-09": "033CFAA2D1F93503",   # 6132 B
    "YEL-STR-NOR-10": "C1CDF7D18A1F87E4",   # 6130 B
    "YEL-SPD-ABN-11": "FA81CAD1B9050A9E",   # 7211 B
    "YEL-SPD-NOR-12": "524CD251936C79B1",   # 7209 B
    "GRN-END-ABN-13": "89842C7A0D8A6EA0",   # 7293 B（不可达的预留位）
    "GRN-END-NOR-14": "3B1DA3AAB8D6A322",   # 5983 B
    "GRN-STR-ABN-15": "91E660991C717944",   # 7092 B（不可达的预留位）
    "GRN-STR-NOR-16": "A5B406807FDEF7CC",   # 5782 B
    "GRN-SPD-ABN-17": "9ADB0CAC53A572F1",   # 7020 B（不可达的预留位）
    "GRN-SPD-NOR-18": "2389C1A03E6ABBCE",   # 5710 B
}
```
18 个文件合计 **123 848 B**（`t3_probes/p06_template_fps.py` 实跑；这个合计**不被断言钉住**，
逐个钉的 18 个值已经蕴含它，再钉一次只增加「改一个模板要多改一行」的成本）。

**选逐个钉、不选拼接钉的四条理由**：

1. 拼接哈希的报错只能说「这 18 个里有东西变了」，而这 18 份文件的**全部意义**就是
   「体育专家可独立审校」（spec §7.2 `:449`）——专家改坏其中一份时必须一眼知道是**哪一份**。
2. **键取 `template_id` 而不是文件名**，于是「把文件改名」也会让本条红（变成
   `FileNotFoundError`），顺带钉住「文件名 == `template_id`」这条约定。
3. 「改一个模板要改一行测试」不是成本而是**用意**：这正是 Task 2 给 `exercises.yaml` 立的
   那道闸——**知识资产的变更必须被显式承认**。
4. 逐个钉让「哪一份被改了」在 `git diff` 里也可见（一行 vs 一行），拼接钉只能看到一个值变了。

**行尾纪律（P3-D2）**：`.gitattributes` 加规则前，`git check-attr text eol --
backend/data/prescription/RED-END-ABN-01.yaml` → `text: unspecified / eol: unspecified`；
加规则后 → `text: set / eol: lf`（三份抽样 + 3 个既有 `data/` 文件全部亲验，见 §11）。
指纹本身先 `replace(b"\r\n", b"\n")` 归一化，故它**守不住**工作树变 CRLF ——
所以另立了 `test_every_template_yaml_is_lf_only_in_the_worktree`（§4.1 的 #22）。

---

## 6. 追加的 `energy_expenditure_plus_5min_hiit` + Task 2 那份 5 项连带清单

**追加了什么**（P3-A4 授权，计划 `:183` 明文允许 Task 3 追加）：

```yaml
energy_expenditure_plus_5min_hiit:
  name: 5 分钟 HIIT 附加模块
  video_url: https://example.invalid/exercise/energy_expenditure_plus_5min_hiit
  impact_level: medium
  targets: [endurance]
  equipment: none
```

**为什么**：黄层 addon 需要它（spec §7.2 `:487`「体脂偏高附加 5min HIIT」），而动作库的
23 个键里没有。**不复用 `hiit`**（P3-A4 的裁定）：`hiit` 是有自己 `impact_level`（high）的
**主项**动作，把「附加 5min HIIT」与「HIIT 主项」混成一个 ref 会让 Task 7 的安全后置无法
区分「换低冲击替身」与「取消追加模块」。理由逐字写进了 `exercises.yaml` 里它自己那节的注释。

**`impact_level: medium` 的理由**：与 `energy_expenditure_plus_10pct` 同构（同一个 `when`、
同一个用途），那一个是 medium；且它是**追加**模块、5 分钟的量不足以构成 high 冲击的关节负荷。

**Task 2 实现者留下的 5 项连带清单逐条兑现**（清单在 `task-2-report.md` **`:639-640`**，
即主体报告 §7「关切与未尽事项」第 9 项；⚠️ 派单 §1.3 说它在 `## fix round 3` 节，
**指向错了**，见 §9 CE-2）：

| # | 连带项 | 兑现情况 |
|---|---|---|
| ① | 同步 `EXERCISES_FINGERPRINT` | **已改**：`63033BBD7F68CC1F` → **`3DE598AF38631209`**；常量上方补了一段说明「Task 3 更新过一次 + 为什么等价表不用动」 |
| ② | 新 ref 若比 `energy_expenditure_plus_10pct`（29 字符）更长，复核 `String(48)` | **触发**：新 ref 是 **33** 字符 > 29，成为本文件最长者。`String(48)` 余量 15，**不需要改声明**（`test_exercise_string_column_widths_fit_the_yaml_values` 现读现比，实跑通过）。已更新 `exercises.yaml` 里「这个 29 字符的名字是本文件最长的 ref」那两行 |
| ③ | 新 ref 若是 `high` 冲击，必须在等价表里给它两个触发各一条 low 映射 + 同步 `EQUIVALENCE_FINGERPRINT` | **不触发**：新 ref 是 medium。`exercise_equivalence.yaml` **字节完全不变**（8 245 B / `822CB86A5E998301` / CRLF 0，`p10_change_surface.py` 逐字节核过），`version` 也不需要升 |
| ④ | `exercises.yaml` 头注释里「条目数 23 的口径」与「high 5 / medium 10 / low 8」那段散文 | **已改**：条目数 23 → **24**（并把 24 拆成「12 + 4 + 7 + 1」，说明第 24 项从哪来）；分布改成 high **5** / medium **11** / low **8** = 24（实跑 `Counter` 核对：`{'medium': 11, 'low': 8, 'high': 5}`）；「本节 5 个条目」→ **6 个**、节标题「两个 addon 模块」→ **三个**；另补「Task 3 已行使那一次追加权，从 Task 4 起追加不再被授权」 |
| ⑤ | 考虑 `version` 是否要升 | **不需要**：`version` 是 `exercise_equivalence.yaml` 的字段，那份文件一个字没改。`exercises.yaml` 自己没有 `version` 字段 |
| — | `>= 20` 那条下界断言 | **不用改**（清单自己说了「这正是我把它写成下界的原因」），实测通过 |

⚠️ **连带的一处我主动改了、但清单没列**：`hiit` 自己的注释原文是「spec §7.2 :487
『体脂偏高附加 5min HIIT』（黄层）。high 冲击，故在等价表里备 low 替身。」——P3-A4 之后
那半句散文的对应物已经**换成新 ref** 了，留着会让下一个人以为 `hiit` 就是那个 addon。
故我把它改成「HIIT **主项**」，并明写「**本条目今天没有任何模板引用它**」（硬规矩 #39），
以及**为什么不删它**（删了等价表的两条映射就悬空、`test_equivalence_table_only_maps_to_existing_exercises`
会红，而那份表的数据部分本 Task 不许动）。→ §10 关切 ②。

**新指纹的取证**（`t3_probes/p04_exercises_fp.py` 实跑）：

```
bytes=22739 CRLF=0 LF=364 sha16(normalized)=3DE598AF38631209
keys=24   has 5min_hiit: True   longest ref: energy_expenditure_plus_5min_hiit 33
impact: Counter({'medium': 11, 'low': 8, 'high': 5})
equivalence bytes=8245 CRLF=0 sha16=822CB86A5E998301      ← 不变
```

---

## 7. domain 覆盖率增量的解释（派单要「你报数 + 解释增量」）

```
                                    基线(c29bc69)   Task 3 后    增量
app/domain/prescription/__init__.py      2 stmts        4        +2
app/domain/prescription/templates.py     2 stmts       58       +56
app/domain/prescription/exercises.py    38 stmts       38         0（一个字没改）
其余 6 个 domain 模块                    399 stmts     399         0
--------------------------------------------------------------------
TOTAL                                  441 stmts      499       +58
Branch                                 120            120         +0
Miss / BrPart                            0 / 0          0 / 0      —
Cover                                   100%          100%        —
```

**+2（`__init__.py`）**：从 1 句 import 变成 3 句（新增 `from app.domain.stratify import Layer`
与 `from .templates import (…)`），`__all__` 那一句不变。

**+56（`templates.py`）**：逐类拆开（`t3_probes/p07_stmt_breakdown.py` 用
`coverage.parser.PythonParser.parse_source()` 取「coverage 认为哪些行是语句」，
再用 AST 给每行归类；两类相加恰为 58）：

| 类别 | 条数 | 是什么 |
|---|---|---|
| `import` | +4 | `collections.abc.Mapping` / `dataclasses.dataclass` / `enum.Enum` / `app.domain.stratify.Layer`（`from .exercises import ImpactLevel` 基线就有） |
| `ClassDef` | +8 | 3 个枚举（`WeaknessBucket` / `BodyCompState` / `ReviewStatus`）+ 5 个 dataclass（`Intensity` / `Block` / `Session` / `Addon` / `Template`） |
| dataclass 装饰器行 | +5 | `@dataclass(frozen=True)` 各占一行（`Expr`/`Call` 节点在装饰器自己的行号上） |
| `AnnAssign` **无值** | +24 | 24 个 dataclass 字段：`Intensity.type` 1 + `Block` 4 + `Session` 3 + `Addon` 2 + `Template` 14。⚠️ **无值的注解也是语句**（CPython 要把注解求值并存进 `__annotations__`，故有字节码），这一点与直觉相反，是 +56 里最大的一块 |
| `AnnAssign` **有值** | +6 | 3 张词表（`TEMPLATE_LAYERS` / `INTENSITY_TYPES` / `ADDON_TRIGGERS`）+ `Intensity` 的 3 个默认值（`low`/`high`/`value = None`） |
| `Assign` | +7 | 7 个枚举成员（3+2+2）；`__all__` 基线就有（改内容不改条数） |
| `FunctionDef` + `Return` | +2 | `is_reachable` |
| | **+56** | |

**branch +0 的原因**（这一条值得写下来，因为它是「100% 分支覆盖」在加了一堆代码之后
**一点没变**的解释）：新增的 12 个公有定义里**没有任何控制流**——枚举成员、dataclass 字段、
`frozenset(...)` 赋值都不产生分支；唯一的函数 `is_reachable` 是一条
`return not (layer is Layer.GREEN and body_comp is BodyCompState.ABNORMAL)`，
而 **coverage.py 的分支分析不在 `return` 内部拆布尔运算符**（它的 arc 图只按
`if`/`for`/`while`/`try` 与条件表达式建弧），故这一句贡献 **1 个语句、0 个分支**。
实测印证：`templates.py` 那行是 `58 stmts / 0 branch / 100%`。

⚠️ **「0 branch」不等于「`is_reachable` 的两个方向没被测」**（硬规矩 #39）：
`test_is_reachable_is_false_for_exactly_the_green_abnormal_cells` **穷举**了 6 个
「层 × 体成分」格并断言为假的恰好是 `[("green","abnormal")]`，另有两条直接断言
`is_reachable(GREEN, NORMAL) is True` 与 `is_reachable(RED, ABNORMAL) is True`；
变异 **M5b** 把它改成 `return True` 之后那条测试确实开了火（§8）。**语句覆盖看不见它、
断言看得见它**——这正是「覆盖率不是断言」的又一例。

**验收命令（带 `--cov-branch`，GC #2）**：
`cd backend; python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing`
→ `TOTAL 499 / Miss 0 / 120 branch / BrPart 0 / 100%`、`580 passed, 1 skipped`。

---

## 8. 变异验收（Step 7）：10 个相位，全部串行

**harness**：`t3_probes/p09_mutate.py`（一次一个相位；`.py` 的变异前后比 `ast.dump`、
`.yaml` 的比 `yaml.safe_load` 结果，**确认变异真的改到了东西**——硬规矩 #53；跑完立刻按
字节复原并核 sha256）。**完整日志**：`t3_probes/mutation_log.txt`（含每个相位的改前/改后
sha、退出码、摘要行、去重后的红名单、真因原文、复原核）。

⚠️ harness 第一次跑 M1 就炸了：锚里写 `\n` 而目标是 **CRLF** 文件、命中 0 次
（`AssertionError: 锚命中 0 次`）。**那次失败没有改动任何文件**，故不构成一个变异相位；
修法是给 `sub_once` 加一个 `nl` 参数、按文件实际行尾归一化锚。同类坑还有两个：
`microcycle_weeks: 4` / `weekly_frequency: 4` / `reachable: false` 三串在**文件头注释里也
逐字出现**（那是「出处」那一段），故锚一律带前导换行。三处都写在 harness 的注释里了。

**干净对照（跑在一切变异之前，硬规矩 #53）**：`581 passed in 59.66s`（退出码 0）。

| 相位 | 变异 | 结果 | **目标判据（哪条断言分支开火）** |
|---|---|---|---|
| **① M1** | `_review()` 里 `ReviewStatus(status)` → `ReviewStatus("approved")`（加载器把 `pending` 静默规范化成 `approved`）。AST 确认变了 | **2 failed, 579 passed** | **`test_loader_preserves_a_pending_review_status_verbatim`**：`AssertionError: assert <ReviewStatus.APPROVED> is <ReviewStatus.PENDING>`。另一条红是 `test_loader_rejects_a_broken_template[review.status]`（`Failed: DID NOT RAISE ValueError`）——**附带判据**，它证明「词表外的第三种值」与「合法的 pending」走的是两条不同的路 |
| **② M2a** | 从 `exercises.yaml` 删掉 `agility_ladder`（**不在**等价表里，只被 2 套绿层模板引用）。解析结果确认变了 | **19 failed, 562 passed** | **`test_every_exercise_ref_exists_in_the_exercise_library`**。真因（加载器抢先开火，正是 Review Focus 第 1 条要的效果）：`ValueError: 处方模板 …\GRN-SPD-ABN-17.yaml 第 73 行：exercise_ref 'agility_ladder' 在动作库里不存在（exercises.yaml 的 23 个键里没有它）…`。另含 `test_exercises_yaml_fingerprint_is_pinned`；**等价表那两条守卫没红**（`agility_ladder` 不是任何映射的端点，与 P3-C1 的预测一致） |
| **② M2b** | 删掉 `interval_run`（**在**等价表里，2 条映射的 `from`，且被 6 套红层模板引用） | **26 failed, 555 passed** | 同上（真因点名 `RED-END-ABN-01.yaml 第 56 行`），**外加** P3-C1 预测的两条跨文件守卫：`test_equivalence_table_only_maps_to_existing_exercises` 与 `test_equivalence_never_maps_to_a_higher_impact_level`。⚠️ 控制者在 Task 2 亲跑的同类变异得 **4 红**，本 Task 得 **26 红**——差值全部来自「模板加载器现在也消费动作库」，即 19 条模板侧测试一起报错 |
| **③ M3a** | `RED-END-ABN-01.yaml` 的 `week_deltas` 4 项 → 3 项 | **19 failed, 562 passed** | 加载器的长度校验：`ValueError: … 第 98 行：week_deltas 有 3 项，而 microcycle_weeks 是 4——两者必须相等…`。⚠️ **简报期望的「长度测试红」是 `test_week_deltas_length_equals_microcycle_weeks`，它确实在红名单里，但是以 error（加载器抛）的形式**，不是它自己的断言开火 |
| **③ M3b** | 同上 + `microcycle_weeks` 也改成 3（让加载器放行，隔离出内容测试） | **2 failed, 579 passed** | **`test_week_deltas_length_equals_microcycle_weeks`**（`AssertionError: RED-END-ABN-01`，开火的是 `microcycle_weeks == MICROCYCLE_WEEKS` 与 `week_deltas == WEEK_DELTAS` 两支）+ `test_template_yaml_fingerprints_are_pinned`。**恰好 2 红**，这就是 ③ 的目标判据 |
| **④ M4a** | `RED-END-ABN-01.yaml` 的 `weekly_frequency` 4 → 3（简报 ④ 的字面做法） | **19 failed, 562 passed** | 加载器的**指导文件档位**校验（不是 session 计数那条，我把档位校验放在计数之前）：`ValueError: … 第 51 行：weekly_frequency 是 3，而 red 层按指导文件应是 4（spec §7.2 :465 …「红 4 / 黄 3 / 绿 2（指导文件原文）」）`。`test_weekly_frequency_follows_the_guidance_document` 在红名单里（以 error 形式） |
| **④ M4c** | **合谋**：加载器的 `_GUIDANCE_FREQUENCY[RED]` 4→3 **且** 那一份 YAML 改成 3 天并删掉 day 4 | **24 failed, 557 passed** | ⚠️ **这个相位没能隔离出测试侧那一份**：另 5 套红层模板的 `weekly_frequency` 仍是 4，加载器照样拒绝它们（真因点名 `RED-END-NOR-02.yaml 第 51 行：weekly_frequency 是 4，而 red 层按指导文件应是 3`）。**这本身是一条有用的发现**：加载器那份表是「任何一套红层模板天数不对」的单点闸门，改坏它一定炸、不可能静默 |
| **④ M4d** | **只改测试侧**的字面量 `GUIDANCE_WEEKLY_FREQUENCY` → `{"red": 3, …}` | **1 failed, 580 passed** | **`test_weekly_frequency_follows_the_guidance_document` 的支 1**：`AssertionError: assert {'red': 3,…} == {'red': 4,…}`。**恰好 1 红**，证明支 1 不是装饰。M4c + M4d 合起来才是硬规矩 #35「两侧刻意不同源」的完整兑现：**任何单侧改坏都有一条守卫接住** |
| **⑤ M5a** | `GRN-END-ABN-13.yaml` 的 `reachable` false → true（简报 ⑤ 的字面做法） | **19 failed, 562 passed** | 加载器的 `reachable` 一致性校验：`ValueError: …GRN-END-ABN-13.yaml 第 61 行：reachable 写的是 True，而 (layer=green, body_comp=abnormal) 这一格按 app.domain.prescription.templates.is_reachable 是 False——两者矛盾（Review Focus 第 1 条点名的坏形状）…`。`test_three_green_abnormal_templates_are_marked_unreachable` 与 `test_template_yaml_fingerprints_are_pinned` **都在红名单里** |
| **⑤ M5b** | 改**规则所有者**：`is_reachable` → `return True`（YAML 一个字不动） | **19 failed, 562 passed** | **`test_is_reachable_is_false_for_exactly_the_green_abnormal_cells`**（`AssertionError: assert [] == [('green','abnormal')]`）+ 加载器对 3 份预留位的拒绝（真因与 M5a 方向相反：`reachable 写的是 False，而 … 是 True`）。⚠️ **与 M5a 的红名单差 1 条、且差的正好是对的那一条**：M5b 里 `test_template_yaml_fingerprints_are_pinned` **不红**（YAML 没改），而 M5a 里它红、`test_is_reachable_…` **不红**。两个相位的红名单**互相鉴别**，说明这两条守卫各自盯着不同的所有者 |

**10 个相位全部按字节复原**（`mutation_log.txt` 里每行 `复原核 … 一致? True`），
复原后重跑 `581 passed`（§2.4 的那一次就是复原之后跑的）。

⚠️ **一条方法论上的发现，报给控制者**：简报 Step 7 的 ③④⑤ 三条都写成「改一个 YAML 字段 →
某条测试红」，而**在真数据上这三条都先被加载器拦下**（Review Focus 第 1 条要求的就是这个），
于是那三条测试是以 **error** 而不是 **assertion failure** 的形式变红。要让「内容测试自己的
断言」开火，必须同时把加载器那道校验绕开（M3b / M4d）——**这不是缺陷，是「两侧刻意不同源」
的必然结果**，但简报的措辞会让人以为一条变异只红一条。故每条我都跑了「字面版」+「隔离版」
两个相位（③ 的 M3a/M3b、④ 的 M4a/M4c/M4d、⑤ 的 M5a/M5b），报告里两版都给了。

---

## 9. 我发现的控制者错误（逐条注明成立 / 不成立 / 歧义 + 证据）

### 9.1 成立

**CE-1（Important）— 派单 §5 自查清单里 `test_models.py` 的四个行号是 `966eae0` 上的、不是代码基线 `c29bc69` 上的；而账本 P3-A11 把这一条记成「核对通过 ✓」。**

派单写：「`test_models.py:169 / :236 / :494` 三处 `== 15`；`:24` 函数名；`:492` 一处注释引用」。
实测（`t3_probes/p01_verify_baseline.py`，同时读 `c29bc69` 的 blob、`966eae0` 的 blob 与工作树）：

| rev | `== 15` 的行 | 函数名引用的行 |
|---|---|---|
| `c29bc69`（**代码基线**，与工作树逐字相同） | **176 / 243 / 501** | **24 / 499** |
| `966eae0` | 169 / 236 / 494 | 24 / 492 |

那四个数字**逐字来自 `966eae0`**——而 `app/db/models/prescription.py:33` 自己就写着
「在**代码基线** `966eae0` 上它们分别是 `:169` / `:236` / `:494` … 与 `:24`」。即这是
**复用历史输出里的行号**，正是硬规矩 #61 扩写（「复用历史输出里的行号等同手写，必须重查」）
要挡的形态，也是 Task 2 fr3 的 I-4 / CE-7 同一个失效形态**第三次**出现。
**「3 处」这个数是对的**（三处真断言），错的只是三个行号 + 注释引用的行号。
账本 P3-A11 那条「`:249`「`== 15` 同样有 **3 处**」→ 实跑在 `:169`/`:236`/`:494` ✓
（函数名 … 在 `:24`，`:492` 另有一处注释引用）」标了「核对通过」，**行数核对了、行号没核对**。
处置：我按实测的 `176 / 243 / 501 / 24 / 499` 改，并把「绑 commit 的行号」与「按可 grep 的
原文找」两套口径都写进了 `test_models.py` 与 `app/db/models/prescription.py` 的注释里，
同时把这次的失效本身记在那里（免得第四次）。

**CE-2（Minor）— 派单 §1.3 说「Task 3 追加 ref 时的 5 项连带清单」在 `task-2-report.md` 的 `## fix round 3` 节，实测在主体报告的 §7。**

`task-2-report.md` 共 1 605 个 LF 行；`## fix round 3` 从 **`:971`** 起。那份 5 项清单在
**`:639-640`**（§7「关切与未尽事项」的第 **9** 项，标题逐字是「**9 — Task 3 追加
`exercise_ref` 时的连带清单（提前写下来，免得它漏）**」）。fr3 节里含「Task 3」字样的只有
`:1593`（账本 P2-A4 的错引用号）与 `:1605`（`test_impact_rank_…` docstring 缺时点），
**都不是那份清单**。清单内容我按 `:640` 逐字执行了（§6），故只是**指向错了节**。

**CE-3（Minor）— 账本 P3-A9 裁定「§7.2 勘误归 Task 3、Task 12 Step 3 的清单相应减一项」，预检小结也说「12 处计划更正已落盘」，而计划文档里 §7.2 勘误那一行仍在 Task 12 的清单里。**

实测 `Document/2026-10-06-实施计划02-智能处方引擎.md`（769 个 LF 行）：

* `:733` 标题已改成「Step 3: spec 勘误与 §14 补项（本 Task 追加 **4 项：#30 / #32 / #33 / #34**）」 ✓
* `:739` §14 清单已写明「**#29 与 #31 已由 Task 3 追加**」 ✓
* **`:741` 仍是「- §7.2 加勘误：指明 `speed_flexibility` 桶的参数空洞。」** ✗ ← 没减掉

于是「§7.2 勘误」这一件事在计划里**同时归属 Task 3 与 Task 12**，正是硬规矩 #75 / #66
要消灭的形态（一个事实出现在两处就要改两处）。**我已按 P3-A9 的裁定在本 Task 写了 §7.2
勘误（6 条，见 §10 前的 §1.2）**，请控制者在 Task 12 派单前把 `:741` 删掉或标注
「已由 Task 3 完成」，否则 Task 12 会第二次写它、并可能与我的 6 条冲突。

**CE-4（Minor）— 派单 §5 那张「待改文件」表一行里混了两个口径而没有标注，表头写的「read_bytes 口径」与 sha 列的实际口径不符。**

派单写「待改文件（**read_bytes 口径**，全部在 `c29bc69` 上量）：`app/refdata_prescription.py`
**23225 B** 413 行 CRLF 413 **`EE0279B00D4AFB1B`**」。实测（`t3_probes/p12_verify_dispatch_table.py`，
12 行逐行核）：`c29bc69` 的 **blob** 是 **22 812 B / LF 413 / CRLF 0 / sha256[:16] =
`EE0279B00D4AFB1B`**；工作树是 23 225 B（= 22 812 + 413 个 CRLF）、其**裸字节** sha256[:16]
是 **`97CD375BF47B7089`**。即：

* `bytes` 与 `CRLF` 两列 = **工作树**值；`行` 与 `sha16` 两列 = **blob（LF）**值；
* 换算关系 `工作树 bytes == blob bytes + CRLF 行数` **12 行逐个成立**；
* 12 个 sha 值**全部**等于 blob 的（= 归一化后的）sha256[:16]，**没有一个**等于工作树裸字节的 sha。

**每个值都是对的，错的是标签**：表头说「read_bytes 口径」，而按 `read_bytes()` 去哈希
`refdata_prescription.py` 得到的是 `97CD375BF47B7089`，与表里印的 `EE0279B00D4AFB1B` 不符。
派单 §0 自己就警告过这件事（「`git show HEAD:<path>` 给的是 **blob 字节**…**字节比对前先
归一化**」），所以这不是不知道，是**没把口径写进那一栏**（硬规矩 #19）。
影响：任何照着那张表去核 sha 的下游都会得到 12 个「不匹配」，然后要么怀疑自己、
要么怀疑文件被改过。建议表头改成「bytes/CRLF = 工作树，行/sha16 = blob（归一化后）」。

### 9.2 不成立 / 歧义（我核过，控制者是对的）

**CE-5（不成立）— 派单 §2 说「3 套 unreachable 要不要有完整 sessions，控制者没法替你定」。**
spec §7.1 `:447` 的②**已经给了答案**：「分层规则未来若调整（例如允许『8 项达标但体成分
异常』者留在绿色层做体成分专项干预），**模板位已就绪**」——「就绪」意味着内容齐全。
故这不是「没法定」，是「依据在 spec 里、需要读出来」。**我按它定了「要有完整内容」，
54 这个数成立并已写成断言**（§3.2）。判为**歧义**（派单把「已有依据」说成了「空缺」，
但把决定权交给我是对的，因为它确实需要一次判断）。

**CE-6（不成立）— 派单 §5 的「12 处待改文件字节数/行/CRLF/sha」逐行核对全部相符**（口径见 CE-4）；
「`.gitattributes` 现有规则 `:13`/`:14`/`:15`/`:38`」逐条相符；
「`git check-attr` 改前 `prescription/RED-END-ABN-01.yaml` → `text: unspecified`」逐字相符；
「`Layer` 四个成员」「`ITEM_BUCKET` 非 None 值三个、最长 17」「动作库 23 个 ref、
有 `hiit`/`energy_expenditure_plus_10pct`/`resistance_priority`/`challenge_task`、
**没有** `energy_expenditure_plus_5min_hiit`」「`SCANNED_DIRS` = 7+11+9 = 27、
`templates.py` 已存在故 domain 仍是 9」——**全部实测相符**。
基线测试态（531 / 441 / 0 / 120 / 0 / 100% / 15 张表 / 530+1 skipped）**逐格相符**。
依赖版本 5 项**逐项相符**。`git diff --name-only c29bc69 ddccba8 -- backend` **实测为空**。

**CE-7（歧义）— 派单 §5 说「task-3-brief.md 35510 B / 202 行」。**
实测 35 510 B ✓、CRLF = 0 ✓；按 `read_bytes().replace(CRLF,LF).split('\n')` 是 **203** 个元素，
按 LF 计数是 **202**（文件以换行结尾）。「202 行」在 LF 口径下成立。同类：派单说
`test_models.py` 757 行，实测 LF = 757 ✓。**记为口径差、不是错误**，但建议以后统一说明
「行 = LF 数」，因为 split 口径永远比它大 1。

**CE-8（歧义）— 派单 §2 说「`templates.py` 加 8 个 dataclass/枚举」，我实际加了 12 个公有顶层定义。**
那 8 个（`WeaknessBucket` / `BodyCompState` / `ReviewStatus` / `Template` / `Session` /
`Block` / `Intensity` / `Addon`）一个不少；**另外 4 个是**：`TEMPLATE_LAYERS` /
`INTENSITY_TYPES` / `ADDON_TRIGGERS` 三张词表 + `is_reachable` 一个纯函数。
**简报的 Produces 清单是下限不是上限**，故这不算控制者错误，但**公开面因此是 7 → 20
而不是 7 → 15**，四处钉死基线的期望值也跟着变，故在此明确交代。四个新增的必要性：

* `is_reachable` —— Review Focus 第 1 条要求加载器拒绝「`reachable: true` 但维度组合不可达」，
  那条规则需要一个住址；放加载器就成了第二个所有者（GC #3），放 domain 则 Task 4 的匹配器
  可以直接复用（spec §7.1 `:447`「不参与匹配」）。
* `INTENSITY_TYPES` / `ADDON_TRIGGERS` —— 若写在加载器里，Task 5/7 就要从 I/O 层取**值类型**，
  而 GC #1 禁止 domain → 非 domain 的 import（`exercises.py` 的 `EQUIVALENCE_TRIGGERS` 就是
  这个理由才住 domain 的）。
* `TEMPLATE_LAYERS` —— 「`Layer` 四个成员里**排除** `INSUFFICIENT`」这个排除声明的唯一住址，
  加载器与 DB 的 CHECK 都消费它。

### 9.3 我自己本轮犯的错（5 条，全部自纠；其中 2 条是被我自己写的断言/闸门拦下的）

1. **两处 grep 计数是我**预测**的、不是实测的**：我在 `test_models.py` 与
   `app/db/models/prescription.py` 里先写下「`== 16` 现命中 **7** 处」「函数名现命中 **4** 处」，
   实跑是 **6** 处与 **5** 处（`p08_selfcheck.py`）。**这正是硬规矩 #29 要挡的「印未实跑的举例」**，
   而我在同一个 Task 里刚把控制者的同类错误记成 CE-1。两处都已按实测改正。
2. **变异 harness 的锚忽略了 CRLF**（M1 第一次跑就炸）与**忽略了「头注释里也有同一串」**
   （M3b/M4a/M5a 的锚会命中 2 次）。前者炸在 `sub_once` 的断言上、后者会炸在同一个断言上，
   **都没有改动任何文件**（断言在写盘之前），故不构成假的变异相位。
3. **加载器的报错里印了一个硬编码的「24 个键」**，而 M2a 删掉一个 ref 之后它变成了 23 个 ——
   报错自己说谎。改成 `{len(library)}`（M2a/M2b 的日志里可以看到它已经正确报「23 个键」）。
   ⚠️ **这条是我自己的变异验收抓出来的**：M2a 的真因原文里那个 24 与当时的事实不符。
4. **`test_sync_templates_updates_a_changed_field_in_place` 的签名里多带了一个用不到的
   `monkeypatch` fixture**（我原本打算改 YAML、后来改成改 DB 行，忘了把参数删掉）。已删。
5. **我在源码 docstring 里逐字复述了被自己撤销的旧断言**（`_PRESCRIPTION_PUBLIC_BASELINE`
   加 `["Template"]` 那一整串），**被自己的落盘闸门抓出来了**：`t3_probes/p14_landing_gate.py`
   的「旧串残留 == 0」那一栏对它命中 1 次。这正是硬规矩 **#74** 要挡的形态——更正说明里抄一遍
   原句，「grep 旧串应当 0 命中」这道闸门就失效了，下一个人分不清「还在用」与「已作废但被引用」。
   已改成描述式（「基线**加上一个当时还不在公开面里的名字**，而它挑的那个名字正是 `Template`」），
   并在源码里明写「被撤销的旧字面量本轮**不再逐字复述**」。⚠️ **本报告 §12.2 仍保留那个旧
   字面量**：报告是审计链、不是源码更正说明，而落盘闸门是**逐文件**的（`p14` 的 32 条 case
   里没有一条查本报告），故不冲突。⚠️ 同一个闸门第一次跑还假红了 3 条，那是**探针自己的缺陷**
   （多行锚用 `\n` 写、而 `backend/**` 的工作树是 CRLF，跨行的锚一律 0 命中），不是磁盘未写；
   修法是串查前先归一化，并按升级口径 ③ 加了一条「查询有效性对照」（用一个已知存在的串验证
   查询本身有效）。**两件事合起来正好说明这道闸门为什么值得跑**：它一次里既抓到了我自己的真
   错误（#74），也暴露了它自己的假阳性来源。
6. **编辑工具对本报告文件的两次写入「报成功而磁盘未写」**，即上面第 5 条那个改动本身第一次
   根本没落盘。取证：改动前先做了字节备份
   `t3_probes/task-3-report.md.bak-before-append`（79 881 B / `1D4555B2D4D22070`），
   两次编辑都回显了 diff，随后 `p15_verify_report_append.py` 实测文件与备份**逐字节相同**、
   新串命中 **0**、旧串「（4 条」命中 **1**。处置：改用 python `read_bytes`/`write_bytes`
   重写（本脚本），写完立刻双向串查（下面打印）。
   ⚠️ **同一轮里对 `backend/tests/test_refdata_prescription.py` 的编辑是真落盘了的**
   （`p14_landing_gate.py` 那条 case 从「旧串=1」变成「旧串=0」），故这不是「工具全局失效」，
   而是**逐次不可信**——唯一可靠的判据是写完立刻用 `read_bytes()` 双向串查（硬规矩 #48 升级口径）。

---

## 10. spec 的改动

### 10.1 §14 追加 **#29** 与 **#31**（编号由 `d40f36c` 预分配，**没有新造号**）

* **#29 — 「18 套模板的审校状态：原型阶段全部标记 `approved` + 占位审校人 + 固定审校日期」**
  默认规定写明了三件事：① 这**不是**审校结果；② 因为 §7.2 `:451`「`!= approved` 拒绝用于
  生成」，这 18 个占位 `approved` 意味着**今天任何一套都能直接给学生生成处方**；
  ③ 审校范围**不限于**改状态，还包括 §7.2 勘误 ② 的空洞（12 套的 `intensity: {type: none}`）
  与「同一套内每一天 `focus`/`blocks` 完全相同」。影响面格点明了 18 份 YAML 被**逐个**指纹
  钉住、`prescription_template` 三列由 `sync_templates` 投影、Task 4 按它决定拒绝。
* **#31 — 「红/黄层 × `speed_flexibility` × 体成分 共 4 套模板的强度与结构参数」**
  点名了那 **4 个文件**（`RED-SPD-ABN-05` / `RED-SPD-NOR-06` / `YEL-SPD-ABN-11` /
  `YEL-SPD-NOR-12`），并明写「改这 4 份要同步 `TEMPLATE_FINGERPRINTS` 里对应那 4 行」、
  「本项被裁决为别的数时**已生成的处方需要重发**（不是重算就能对上的）」。
  ⚠️ 我还在这一格里登记了一个**比原空洞更大的空洞**：`structure` 的键**没有任何 spec 条文
  定义语义**，而 Task 6 的装配器必须认得 `sets`/`work_min`/`rest_min`/`rounds`/`reps` 五个键。

**表后另加一段说明「#30 的空洞是刻意的」**：#29/#31 由 Task 3 写入、#30/#32/#33/#34 留给
Task 12，故本表在 Task 12 落地之前是「1–29 + 31」，**缺 #30 不是丢了一项**；总数仍是
`27 + 1(#28, T2) + 2(#29/#31, T3) + 4(T12) = 34`。

### 10.2 §7.2 勘误（**6 条**，P3-A9 裁定归本 Task）

放在 `:487` 那行散文（「指导文件给出的层级参数**已全部**落入模板」）之后，格式照 Plan 01
的勘误（原文 + 更正 + 理由 + §14 编号）：

| # | 一句话摘要 |
|---|---|
| ① | **`speed_flexibility` 桶没有任何参数**（红/黄层共 4 套）→ 动作选自速度柔韧类、强度借用同层耐力配置 → **§14 #31** |
| ② | **整个黄层与整个绿层都没有强度数值**（不只是速度柔韧桶）→ 12 套的每个 block 写 `intensity: {type: none}`（显式取值，不是留空）；红层力量的 `plyometric_jump` 同理（1RM 是杠铃类概念）→ 并入 **§14 #29** 的审校范围，不另占编号 |
| ③ | **`reachable` 不在 §4.4 `:238` 的字段清单里**（P3-A10）→ 表与 YAML 都增补这一列，依据在 **§7.1 `:447`** 而不是 §4.4；同时点明 Task 12 那条「§4.4 用 `template_ref` 而不是 YAML 路径」的勘误与本条不重复 |
| ④ | **绿层 `addons` 为空**，于是 §7.4 `:510` 的第三个触发对绿层学生**无模块可追加**；今天不可达（绿层必然 `NOT C`），但 `:510` 没写层限定，**分层规则一调整就是真漏洞** → 报为关切（§11 ③） |
| ⑤ | **`version` 与 `reviewed_at` 必须加引号**：不加引号 PyYAML 会把 `1.0` 读成 float（`1.10` → `1.1`）、把 `2026-10-06` 读成 `datetime.date` |
| ⑥ | **`template_id` 末两位序号的定序规则骨架没给** → 全局序号 01–18，枚举序 = 层 × 短板 × 体成分（**异常在前**，为了让骨架那个字面示例原样重现）；三字母缩写除 `END`/`ABN` 外由本 Task 定 |

---

## 11. `.gitattributes`（P3-D2）改前改后的亲验输出

**加的规则**（放在 `backend/data/*.md` 那一条之后，与既有的 `backend/data/*.yaml` 并存；
gitattributes 后写的优先，故 `**` 那条必须在后面）：

```
backend/data/**/*.yaml text eol=lf
```
连同 11 行注释解释「为什么必须加」（`*` 不跨 `/`、Plan 01 国标评分表事故的原型、
亲验命令）。`.gitattributes`：38 行 → **50 行**，4 385 B，CRLF 50，**0 个裸 LF**
（`t3_probes/p03_gitattributes.py` 用 `read_bytes()` 核）。

**改前**（控制者的输出，我复跑逐字相符）：
```
$ git check-attr text eol -- backend/data/exercises.yaml
backend/data/exercises.yaml: text: set
backend/data/exercises.yaml: eol: lf
$ git check-attr text eol -- backend/data/prescription/RED-END-ABN-01.yaml
backend/data/prescription/RED-END-ABN-01.yaml: text: unspecified
backend/data/prescription/RED-END-ABN-01.yaml: eol: unspecified
```

**改后**（我实跑，抽样 3 个模板 + 3 个既有 `data/` 文件 + 1 个 `.superpowers/` 路径）：
```
backend/data/prescription/RED-END-ABN-01.yaml: text: set        eol: lf
backend/data/prescription/YEL-SPD-NOR-12.yaml: text: set        eol: lf
backend/data/prescription/GRN-SPD-NOR-18.yaml: text: set        eol: lf
backend/data/exercises.yaml:                   text: set        eol: lf
backend/data/exercise_equivalence.yaml:        text: set        eol: lf
backend/data/national_standard_2014.csv:       text: set        eol: lf
.superpowers/sdd/x/task-3-report.md:           text: unset      eol: unspecified   ← -text 未被波及
```

**`git ls-files --eol -- backend/data/`**（18 个模板入库后重跑，见 §12）：每一行都是
`i/lf    w/lf    attr/text eol=lf`，**不合此形状的行数 = 0**。

⚠️ **入库前跑这条命令只列出 5 个文件**（18 个模板还是 untracked，`ls-files` 看不见）——
这不是规则没生效，`check-attr` 对路径模式求值、不要求文件被跟踪（正是控制者 P3-D2 用的
那个性质）。故我在 commit **之后**重跑了它并把输出贴在 §12。

**双重保险的分工**（写进了两条测试的 docstring）：`.gitattributes` 的规则保证「检出成 LF」，
`test_every_template_yaml_is_lf_only_in_the_worktree` 保证「工作树里真的是 LF」，
指纹的 `replace(b"\r\n", b"\n")` 保证「即使前两道都失效，指纹也不随平台漂」。
**第二条是不可省的**：指纹归一化之后，工作树全变 CRLF 它照样绿。

---

## 12. 四处钉死基线的更新（P3-A6）

| # | 位置 | 改前 | 改后 | 是否保持「字面写死」 |
|---|---|---|---|---|
| 1 | `test_refdata_prescription.py` `_PRESCRIPTION_PUBLIC_BASELINE` + `assert len(...) == 7` | 7 个裸名字 | **20** 个 `(名字, 所有者模块点号串)` 二元组 + `assert len(...) == 20` + `assert len(set(names)) == 20` | **是**。仍是字面清单，**没有**改成 `list(pkg.__all__)` |
| 2 | 同文件 `:951-952` 两条负向断言 | `!= baseline + ["Template"]` / `!= baseline[:-1]` | `!= names + ["__NOT_IN_THE_PUBLIC_FACE__"]` / `!= names[:-1]` | **是**（哨兵是字面量） |
| 3 | `test_prescription_templates.py:152` `templates.__all__ == ["ImpactLevel"]` | 1 个名字 | **14** 个名字（字面清单，含声明序） | **是** |
| 4 | `test_generate.py` `REFERENCE_TABLES` | `("exercise",)` | `("exercise", "prescription_template")`（**定义与 `assert` 两处同步**） | **是** |

### 12.1 为什么基线要从「裸名字」变成「(名字, 所有者)」二元组

原来的支 4 是 `for name in baseline: owner = getattr(exercises_mod, name); assert getattr(pkg, name) is owner`
——它把**所有者模块硬编码成了 `exercises_mod`**。Task 2 时 7 个名字的所有者恰好都是
`exercises`，所以那样写没问题；Task 3 之后公开面横跨**三个**所有者
（`exercises` / `templates` / `stratify`），再硬编码一个模块会让新名字全部
`getattr(...) is None`。把所有者写进基线之后**两侧仍然都是字面量**（基线是手写的、
`importlib.import_module(owner)` 只是按字面串取模块），不构成 #35 的同源。

顺带**多了一个失效方向**，我在支 5 的注释里点明了：谁把基线里某一项的所有者写错
（例如把 `Layer` 的所有者写成 `templates`）→ **支 5 红**（`templates.py` 里没有 `Layer` 的
**定义**，它是 import 进来的），而**支 4 仍然绿**（`templates.Layer is stratify.Layer` 成立）。
故支 4 与支 5 现在各守一个方向、缺一不可。

支 5 的穷尽判据也只对 `_OWNED_MODULES = (exercises, templates)` 成立：`Layer` 的所有者
`app.domain.stratify` 有一批自己的公有顶层定义（`RULE_ORDER` / `RuleId` / `Stratification` /
`stratify` …），本包只借它一个 `Layer`，「凡公有顶层定义都必须被重导出」对它根本不成立。
主语写进了 `_OWNED_MODULES` 的注释（硬规矩 #56）。

### 12.2 `:951` 那条的用意（派单要求「重新想并在报告里说明理由」）

**它原来想挡什么**：Task 2 fr2 写 `!= _PRESCRIPTION_PUBLIC_BASELINE + ["Template"]`，
挑 `"Template"` 正因为**当时公开面里没有这个名字**——于是「基线 + 一个还没有的名字」是一个
**可合成的失同步态**，用它证明支 2 那条相等断言对「多一个」敏感、不是恒真式（硬规矩 #50 的红输入）。

**Task 3 之后它出了什么问题**：`Template` 真的进了公开面。`names + ["Template"]` 变成一个
**含重复元素的 21 项清单**。它确实仍不等于 `list(__all__)`（长度就不同），**断言不会假绿**；
但它不再是「多一个**新**名字」的合成态，而是「多一个**已有**名字」——**守的东西悄悄换了**，
而下一个人读到 `+ ["Template"]` 会以为那是在挡「不许有 Template」（派单也正是这么读的）。

**我的改法**：换成 `"__NOT_IN_THE_PUBLIC_FACE__"`——一个**刻意不可能成为真名字**的哨兵
（前后双下划线；且 `from … import *` 也不会导出它，故它永远不可能出现在任何 `__all__` 里）。
于是支 6a 的语义**永久稳定**：「基线 + 一个绝不可能在公开面里的名字 ≠ 实际公开面」，
Task 4 加 `MatchResult`、Task 9 加别的名字都不会再让它失效或改变含义。
**用意在支 6 的注释与那条测试的 docstring 里都写了**（「它要挡的是『把基线写成当前 `__all__`
再去掉一个』这类恒真式，不是『永远不许有 `Template`』」）。
支 6b（`!= names[:-1]`）**一个字没改**：它守的是「少最后一个名字」，与名字是什么无关
（Task 2 的 M-C1 实测它真的开过火）。

### 12.3 另外三处「字面钉死」的连带更新（派单没点、但不改就是假陈述）

* `test_models.py`：`== 15` → `== 16` 共 **6** 处（3 处真断言 + 3 处引 grep 命令的散文，
  实测计数见 CE-1 的处置）；`test_all_fifteen_tables_created` → `test_all_sixteen_tables_created`
  （`git grep` 旧名 **0 命中**、新名 **5 命中**）；`expected` 集合 +`"prescription_template"`；
  `test_no_column_uses_builtin_sqlalchemy_json` docstring 的「遍历 15 张表」→ 16；
  `json_text_columns == 9` **不变**（新表 10 列全是 String/Date/Boolean/int，**没有 JsonText 列**，
  已在注释里点明这正是 P2-A6 的教训）；`test_string_column_widths_fit_their_value_domains`
  docstring 的「今天 **11** 列」→ **15** 列并列出新增的 4 个列名（`>= 10` 那个**下界**按它
  自己的注释「刻意不逐 Task 抬高」，**没动**）。
* `app/db/models/prescription.py`：模块 docstring 的「表 → 归属 Task」表把
  `prescription_template` 标成 **已建**；grep 指引整套改成 `== 16` / `test_all_sixteen_…`；
  「`exercise` …是本小节**唯一**一张参考数据表」→「**仅有的两张**」（硬规矩 #66：一个事实
  变了要 grep 出全部同类陈述逐个更新）。
* `app/db/models/__init__.py`：`test_all_fifteen_tables_created` 的按名引用改成新名，
  并把「Plan 02 新加的表类（今天是 `Exercise`）」改成「`Exercise` 与 `PrescriptionTemplate`」，
  同时点明 Ruling 97 那条纪律对 Task 3 同样成立、守卫是哪一条。**`__all__` 一个字没动**
  （33 个名字的基线不变，`test_models_public_namespace_is_unchanged_by_the_split` 实跑绿）。

---

## 13. 改动面自证（硬规矩 #32，**带对照组**）

`t3_probes/p10_change_surface.py` 实跑，总判定 **PASS**：

| 判据 | 结果 |
|---|---|
| `refdata_prescription.py`：既有 12 个顶层定义（`_exercise_spec` / `load_exercises` / `exercises` / `_equivalence_mapping` / `load_equivalence` / `equivalence` / `sync_exercises` / `_EXERCISE_KEYS` / `_MAPPING_KEYS` / `_REF_SHAPE` / `EXERCISES_FILENAME` / `EQUIVALENCE_FILENAME`）**AST 逐字不变** | ✓ 新增恰好是我列的 30 个、**删除 0 个** |
| `app/domain/prescription/exercises.py` **归一化字节完全相同** | ✓ 基线与现状都是 `3E13D9E322C9D9A4` |
| `app/db/models/__init__.py` 剥模块 docstring 后 **AST 相同**（即只改了注释） | ✓ |
| `app/db/models/prescription.py`：`Exercise` 类 **AST 逐字不变**、只新增 `PrescriptionTemplate` | ✓ 删除 0 个 |
| `exercises.yaml`：既有 **23** 个条目**逐字不变**、只多 1 个键 | ✓ 新增 `['energy_expenditure_plus_5min_hiit']`、删除 `[]`、**既有键里值漂了的 `[]`** |
| `exercise_equivalence.yaml` **归一化字节完全相同** | ✓ `822CB86A5E998301` |
| `national_standard_2014.csv` **归一化字节完全相同** | ✓ `D2C8E539E2FA0029` |
| **对照组**（硬规矩 #53：闸门自己有牙吗） | 往 `load_exercises` 注入「只取前 3 个动作」（`list(raw.items())[:3]`）后，本闸门的 AST 比对**判为不同**（必须是 False）→ ✓ 闸门不是恒真 |

---

## 14. 收工自证

```
$ git status --short                      → 0 行（commit 之后）
$ git log --oneline -1                    → 本轮那一个 commit
$ python -c "…Base.metadata.tables"       → 16
$ python -m pytest -q                     → 581 passed
$ --cov=app.domain --cov-branch           → TOTAL 499 / Miss 0 / 120 branch / BrPart 0 / 100%
                                            580 passed, 1 skipped
禁区：
  backend/pe.db 存在?                     → False
  backend/data/seed/ 文件数               → 0（目录存在、0 文件，与基线同）
  national_standard_2014.csv              → 21412 B / CRLF 0 / D2C8E539E2FA0029   ✓ 不变
  exercise_equivalence.yaml               → 8245 B / CRLF 0 / 822CB86A5E998301     ✓ 不变
  没跑过 python -m app.seed.generate / app.pipeline.backfill / app.pipeline.daily
无临时目录残留：变异全部走 tmp_path 或 harness 内复原；t3_probes/ 是**入库的取证脚本**、
  不是临时目录（派单 §3 指定了这个名字）
```

---

## 15. 关切与未尽事项

**① 「带进 Task 3 的清单」10 项里，我只做了 5 项，另 3 项**没做**、2 项不适用。逐条交代。**

| 项 | 内容 | 处置 |
|---|---|---|
| ④ | `templates.py` 是 Modify 不是 Create | **已做**（§1.2） |
| ⑤ | `impact_level` 的所有者是 `exercises.yaml`，模板加载器必须校验一致 | **已做**（加载器 + 用例 ⑨ + `test_every_block_impact_level_matches_the_exercise_library`） |
| ⑥ | Task 3 追加 ref 要同步 `EXERCISES_FINGERPRINT` | **已做**（§6） |
| ⑦ | 两份 `__all__` 必须一起改 | **已做**（§12，第三份基线也一起改了） |
| ⑨ | Plan 02 新表不进 `models` 公有导入面 | **已做**（`__all__` 未动 + 新守卫 #12） |
| ⑩ | 若写 `level == 2` 相对导入，全仓计数 15 → 16、散文要再更新 | **不适用**（我选了绝对导入，计数仍是 15、`{1: 15}`，两个架构测试一个字没改，见 §3.6） |
| ① | `cases` 矩阵换成「扫真仓每个 `.py` 与 `resolve_name` 对拍」 | **没做**。它要改 `tests/architecture/test_domain_purity.py` 与 `test_layering.py`，那两个文件**不在简报 Task 3 的 Files 段里**，也不在派单 §2 的交付清单里。改它们等于扩大授权改动面 |
| ② | `_package_of` 的断言换成扫真仓与 `py.relative_to(BACKEND).parent.parts` 对拍 | **没做**，同上 |
| ③ | `lookup()` 的分支测试搬到 `tests/domain/test_prescription_exercises.py` | **没做**。计划的 File Structure「新建（测试）」里没有 `test_prescription_exercises.py` 这个文件，Task 3 的 Files 段也没有。**新建它会撞 Task 4-9 的命名空间**（那个文件名暗示它该由建 `exercises.py` 相关守卫的 Task 来做）。⚠️ 我已在 `tests/test_refdata_prescription.py` 的文件 docstring 里把这件事标成「Task 3 没有做这次搬迁」并说明理由，免得下一个人以为已经搬过了 |
| ⑧ | `test_impact_rank_values_are_pinned_verbatim` 的 docstring 缺时点 | **没做**。派单没授权、简报没点，且改它要重写那段的时间态表述（Task 2 fr3 的实现者自己也判断「超出本轮范围，报给控制者」）。**建议并入 Task 4 的散文清扫** |

**请控制者裁定 ①②③⑧ 归哪个 Task。** 我的建议：①② 归 Task 4（它要建 `match.py`、
届时 `app/domain/prescription/` 的相对导入形状会真的变，正是重写那两段散文的时机）；
③ 与 ⑧ 可以并成一次「domain 测试归位」的小 Task，或并进 Task 12 的散文清扫。

**② `hiit` 今天没有任何模板引用它，而它在等价表里有两条映射。**
P3-A4 把黄层 addon 拆给了新 ref `energy_expenditure_plus_5min_hiit`，于是 `hiit` 从
「黄层体脂偏高的附加模块」变成了「一个没有消费者的主项动作」——指导文件没有把 HIIT 列为
任何「层 × 短板」的主项。**不删它**：删了 `exercise_equivalence.yaml` 的两条映射
（`hiit → functional_training`，两个触发各一条）就悬空，
`test_equivalence_table_only_maps_to_existing_exercises` 会红，而那份表的**数据部分**本 Task
不许动。已在 `exercises.yaml` 里 `hiit` 自己的注释里写明这件事（硬规矩 #39）。
**请裁定**：要么将来某一套模板用它（例如黄层耐力加一个 HIIT 主项），要么连同两条映射
一起下线（那要升 `version`）。

**③ 绿层 `addons: []` 让 spec §7.4 `:510` 的第三个触发对绿层学生无模块可追加。**
今天不可达（绿层必然 `NOT C`），但 `:510` 没写层限定，**分层规则一调整就是真漏洞**
（触发命中、addons 为空、于是「追加能量消耗模块」静默无事发生）。已写进 spec §7.2 勘误 ④。
**本 Task 只被授权追加 #29 与 #31，故没有自行占一个 §14 编号**——请裁定它是否值得单列
（若单列，Task 12 的 4 项清单与「27 → 34」那个总数都要跟着改）。

**④ `energy_expenditure_plus_5min_hiit`（medium、无映射）与主项 `hiit`（high、有两条映射）的不对称。**
后果：一个 BMI > 30 的黄层学生会看到「主项 HIIT 被换成低冲击的功能性训练，而**追加的那个
5min HIIT 模块原样保留**」。这是 P3-A4 那条裁定（不复用 `hiit`）的直接后果、不是疏漏。
要消除它得让 Task 7 对 addon 也做一次冲击检查，而 spec §7.4 `:510` 只写了「追加模板 addons
中的能量消耗模块」、没写要检查冲击。**请在 Task 7 的预检里裁一次。**

**⑤ `structure` 的键没有词表，Task 6 必须自己认得那五个键。**
spec 只给了两个字面字典例子（`:473` / `:477`），没给键的取值域。我**没有编一个词表**
（编了就是第二个所有者，且会被下游当成 spec 条文），加载器只校验「非空映射 + 键全是字符串」。
已登记进 §14 **#31** 的影响面格。**Task 6 落地时若要给 `structure` 立词表，请先回改 §14 #31。**

**⑥ 18 套模板里同一套的每一天 `focus` 与 `blocks` 完全相同。**
指导文件按「层 × 短板」给参数、**没有**按周内第几天给，故没有分化的依据；要分化需要专家
给参数。已并入 §14 **#29** 的审校范围，也写进了 `Session.focus` 的 docstring 与 18 份 YAML
的头注释。**风险**：一份「四天完全一样」的红层处方在体育教学上是不合理的（同一刺激连续
四天没有恢复窗口），但**改它就必须编造参数**，两害相权我选了「不编造 + 显式登记」。

**⑦ `Intensity` 的 `rpe` 档今天没有任何真数据用例。**
词表里有它（简报 Produces 逐字列举的四个之一）、加载器也校验它的字段形状（`value` 必填），
但 18 套模板里没有 `{type: rpe}` 的 block（指导文件没给 RPE 目标值）。
**故 `_INTENSITY_FIELDS["rpe"]` 那一行不被真数据走过**，只被合成用例与词表断言覆盖。
已在 `_INTENSITY_FIELDS` 的注释里写明（硬规矩 #39）。它是给 Plan 03 的预警侧留的位置
（spec §8.2 的课堂快评 RPE 0–10 用同一套语义）。

**⑧ 账本 P2-A4 的错引用号（`progress.md:999` 那句「Plan 01 Ruling 19 的口径」）按 Task 2 fr3 的请求归控制者改。**
本轮我**没有**照账本抄：`WeaknessBucket` 与 `PrescriptionTemplate.WEAKNESSES` 的注释里，
「BMI 不归任何短板桶」的出处一律写 **spec §4.2**（那张「8 项原始测量」表的 BMI 行 +
同节说明「短板判定项 = 6 个（排除 BMI）」），与 `exercises.py` 已更正的口径一致。
**没有第三次传播。**

**⑨ 一处我没改、但认为该报的过期散文（超出授权改动面）。**
`tests/architecture/test_domain_purity.py:369-371` 与 `test_layering.py:386-388` 各有一格
合成用例，注释写「Task 2 会新建 `app/domain/prescription/` 子包（**今天不存在**）」——
那个子包 Task 2 就建出来了，「今天不存在」现在是假的（Task 2 fr5 加这两格时它就已经存在）。
两格用例本身是**正确的**（`_package_of` 对包深 3 的折算），只是注释的时间态过期了。
那两个文件不在本 Task 的授权改动面里，故没动。**建议并入上面 ①② 那次改写。**
