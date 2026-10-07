# Task 2 收尾评审（动作库）— `fb5bddb..966eae0`，代码基线 `966eae0`，HEAD `7296793`

> 评审者：任务评审者（read-only）。**未修改任何入库文件**；全部探针写在
> `.superpowers/sdd/review2_probes/`（14 个 `.py` + 7 个 `.txt` 输出）与 `$env:TEMP`。
> 行号一律 **shell 口径**（`read_bytes()` → `replace(b"\r\n", b"\n")` → `split("\n")`），
> 未使用 `Read` 工具打开任何 `.superpowers/` 下的大文件（硬规矩 #69）。
> 落盘方式：IDE 写文件工具（UTF-8，无换行翻译），落盘后立即用 python `read_bytes()` 读回并做双向串查（见文末 §7）。

---

## 0. ⚠️ 先报一件影响取证范围的事：本机 `pytest` 全量已跑不起来（环境级阻塞，非本仓缺陷）

**现象**：`cd backend; python -m pytest -q` → `12 errors during collection`，退出码 2。

```
tests\db\test_models.py:6: in <module>
    from sqlalchemy import JSON as BuiltinJson, create_engine, inspect, select, text
C:\Python\Lib\site-packages\sqlalchemy\sql\cache_key.py:29: in <module>
    from . import _cache_key_cy
E   ImportError: DLL load failed while importing _cache_key_cy: 应用程序控制策略已阻止此文件。
```

**根因（已定位到 Windows 事件日志，非推测）**：

```
LogName : Microsoft-Windows-CodeIntegrity/Operational
TimeCreated : 2026/10/7 21:45:55     Id : 3077 / 3033 / 3118
Code Integrity determined that a process (\Device\HarddiskVolume3\Python\python.exe)
attempted to load \Device\HarddiskVolume3\Python\Lib\site-packages\sqlalchemy\sql\
_cache_key_cy.cp311-win_amd64.pyd that did not meet the Enterprise signing level
requirements or violated code integrity policy
(Policy ID:{0283ac0f-fff1-49ae-ada1-8a933130cad6}).
Id 3118 : Smart App Control Block Deteails
```

即 **Windows Smart App Control（WDAC）按文件级策略封掉了 `sqlalchemy/sql/_cache_key_cy.cp311-win_amd64.pyd` 这一个 `.pyd`**。取证：

| 项 | 实测 |
|---|---|
| 8 个 sqlalchemy `.pyd` 的 mtime | **全部 `2026-09-28 18:00:17`**（安装时刻，一个都没被改过） |
| `import sqlalchemy.util._immutabledict_cy` | **OK** |
| `import sqlalchemy.sql._util_cy` | **OK** |
| `import sqlalchemy.sql._cache_key_cy` | **FAIL**（同一个错误串） |
| 把该 `.pyd` 复制到 `$env:TEMP\rv2_ck\` 后用 `ExtensionFileLoader` 加载 | **FAIL**（同错误）→ 策略按内容/签名，不按路径 |
| `sqlalchemy` 版本 / Python | **2.1.1** / **3.11.1**（`C:\Python`，无 venv） |
| `sqlalchemy/sql/cache_key.py:29` | `from . import _cache_key_cy` **无 try/except、无纯 Python 回退** |

**结论**：磁盘上的文件一个字节没变，是**机器策略**在控制者上一次成功跑完 `531 passed` 之后变了。
评审者**没有**采取任何绕过手段（不改 site-packages、不装另一个 SQLAlchemy 版本、不给
`_cache_key_cy` 塞 stub 模块）——那些做法会让"我跑出来的绿"与被评审的代码脱钩，
比不跑更坏。**解除阻塞需要用户/管理员关掉 Smart App Control 或把该 `.pyd` 加进策略白名单。**

**仍然可跑的部分（本报告的所有实跑证据都来自这里）**：

| 能跑 | 为什么能跑 |
|---|---|
| `python -m pytest -q tests/domain/test_prescription_templates.py tests/architecture/test_domain_purity.py tests/architecture/test_layering.py` → **`10 passed in 0.12s`**、退出码 0 | 这 3 个文件都不 import sqlalchemy |
| 上述单文件 + `--cov=app/domain/prescription --cov-branch --cov-report=term-missing` | 覆盖率只碰 domain 子包 |
| `import app.domain.prescription{,.exercises,.templates}`、`import app.domain.indicators`、`import yaml` / `numpy` / `pandas` / `sqlite3` | 全部 OK |
| `importlib` 直接加载两份架构守卫模块，调用它们的 `_is_allowed` / `_is_forbidden` / `_absolute` / `_package_of` / `_domain_files` / `_py_files` | 全部 OK |
| `git show <rev>:<path>` + `git ls-tree`（不 checkout） | 全部 OK |

**不可跑** → 见 §6「不可复核项」（12 条）。

---

## 1. Spec 合规：Task 2 的验收判据是否满足

### 1.1 简报 Task 2 全节（Step 1–5）

| 判据 | 实测 | 判定 |
|---|---|---|
| Step 1：从 spec §7.2:487 点名的动作 + 18 格矩阵推出动作库，**不从 Task 3 的 YAML 反推** | 16 个骨架动作全部在库（见 §1.2 的逐名映射）；`backend/data/prescription/` **不存在**（Task 3 未开工） | ✅ |
| Step 1：`exercise_ref` 唯一所有者 = `exercises.yaml` 键集 | `exercises.yaml:6` 明写；`ExerciseSpec` docstring `:114-117` 明写 + 指明校验方为 Task 3 加载器 | ✅ |
| **Step 1 / P2-B2：`ExerciseSpec.impact_level` 的 docstring 要写明自己是所有者、谁负责校验** | `exercises.py:119-124`：「**本字段是「这个动作是哪一档冲击」的唯一真相**…**负责校验一致的是 Task 3 的模板加载器**…加载器 `app.refdata_prescription` 只加载动作库、看不到模板，故校验不住这件事」 | ✅ **逐字满足**（P2-B2 的三个要素：所有者 / 校验方 / 本模块守不住什么，全在） |
| Step 2：6 条测试（含 P2-C2 改名） | 6 条全部存在，名字逐字相符；`test_every_high_impact_exercise_has_a_low_substitute`（改名后）在 `:352` | ✅ |
| Step 2：指纹先归一化再哈希 | `test_refdata_prescription.py:100-102` = `hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16].upper()` | ✅ |
| Step 3：`exercise_equivalence.yaml` 顶层 `version: "1.0"` + `mappings[{from,to,max_impact,when}]` | 实测 `version = '1.0'`（**字符串**，加引号）、10 条映射每条恰好 4 键 | ✅ |
| Step 3 / Ruling 7：`volume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}` + 字面钉住 | 实测逐字相符；`test_volume_reduction_coefficients_are_pinned_verbatim:427-428` 字面写死 `0.8` / `0.9` | ✅ |
| Step 3 / P2-A3：两个系数在 YAML 注释与 spec §14 双双登记「无 spec 出处」 | `exercise_equivalence.yaml:51-59`（含 `:604` 那个假类比的显式否认）+ `spec:933`（§14 第 28 项） | ✅（但 §14 那一项的**编号交代已过期**，见 I-7） |
| Step 4：`.gitattributes` **只确认不改** | `git diff --name-only fb5bddb..966eae0 -- .gitattributes .gitignore` → **空**；两个 YAML 实测 **CRLF = 0**（纯 LF），落进 `.gitattributes:14` 的 `backend/data/*.yaml text eol=lf` | ✅ |
| Step 4：`Exercise` 6 列（`ref` String(48) unique / `name` String(64) / `video_url` String(256) / `impact_level` String(8)+CHECK / `targets` JsonText / `equipment` String(32)） | AST 逐列读出，**逐字相符**（`prescription.py:114-127`）；CHECK 名 `ck_exercise_impact_level` | ✅ |
| Step 4 / P2-A5：4 个无 CHECK 列另写列宽断言 | `test_refdata_prescription.py:531-563`，且带 `:563` 的空转自校 `assert len(longest) == 4` | ✅ |
| Step 4 / P2-A6：`== 14` 3 处 → `== 15`、函数名改 `fifteen`、跨文件按名引用同步 | `== 15` **3 处**（`:169`/`:236`/`:494`）、`def test_all_fifteen_tables_created` 在 `:24`、`git grep fourteen -- backend` → **0 命中**、4 处按名引用全部是 `fifteen` | ✅ 改到位（⚠️ 但**散文里印的行号没跟着改**，见 I-4） |
| Step 5 / P2-A1：不新建 `app/seed/prescription.py`、不改 `seed_database`、灌数据函数叫 `sync_exercises(session)` 且住 `refdata_prescription.py` | `git diff --name-only fb5bddb..HEAD -- backend/app/seed` → **空**；`sync_exercises(session: Session) -> int` 在 `refdata_prescription.py:366` | ✅ |
| Step 5 / P2-A1：分区穷尽守卫 + `REFERENCE_TABLES == ("exercise",)` | `test_generate.py:496` `REFERENCE_TABLES = ("exercise",)`；`:499 test_table_partition_is_exhaustive`；`:518-519` `set(ORGANISATION_TABLES) | set(DATA_TABLES) | set(REFERENCE_TABLES) == set(models.Base.metadata.tables)`；`:533` 字面钉住 `("exercise",)`；**另加**互不相交断言（`:528-531`，裁定没要求） | ✅ **超出裁定** |
| Step 5 / P2-C1：变异 ② 只验指纹 | `exercises.yaml:259-261` 与 `test_refdata_prescription.py:26-28` 都写明「只有指纹会红」、并指明模板引用存在性归 Task 3 | ✅ |
| Step 5 / D3：不跑三个 CLI | `backend/pe.db` **不存在**、`backend/data/seed/` **0 文件**（两个后果性证据都在） | ✅（"跑没跑"本身不可复核，见 §6-9） |

### 1.2 spec 合规（§4.4 / §7.2 / §7.4 / §14）

**`Exercise` ORM ↔ spec §4.4 `:239`**（spec 原文：「`exercise` | id、动作名、视频二维码 URL、**`impact_level`** ∈ {`high`, `medium`, `low`}、目标素质、器械需求」）：

| spec §4.4:239 | 列 | 声明 | 判定 |
|---|---|---|---|
| id | `id` | `Mapped[int] primary_key` | ✅ |
| 动作名 | `name` | `String(64)` | ✅ |
| 视频二维码 URL | `video_url` | `String(256)` | ✅ |
| `impact_level` ∈ {high,medium,low} | `impact_level` | `String(8)` + `_in_domain("impact_level", IMPACT_LEVELS, "ck_exercise_impact_level")`，`IMPACT_LEVELS = {"high","medium","low"}` | ✅ |
| 目标素质 | `targets` | `JsonText` | ✅ |
| 器械需求 | `equipment` | `String(32)` | ✅ |
| （spec 未点名，计划 Step 4 要求） | `ref` | `String(48), unique=True` | ✅ `prescription.py:69-72` 交代了为什么用 `ref` 而不是 `id` 做引用键 |

**23 个动作对 spec §7.2 `:487` + 计划「速度柔韧类 4 个」的覆盖**（逐名实测，全部命中）：

| 出处 | 中文名 | ref |
|---|---|---|
| :487 | 间歇跑 | `interval_run` |
| :487 | 复合循环 | `compound_circuit` |
| :487 | 持续跑 | `steady_run` |
| :487 | 台阶训练 | `step_training` |
| :487 | 自重抗阻 | `bodyweight_resistance` |
| :487 | 弹力带抗阻 | `band_resistance` |
| :487 | 兴趣球类 | `interest_ball_games` |
| :487 | 定向越野 | `orienteering` |
| :487 | 功能性训练 | `functional_training` |
| :487 | HIIT | `hiit` |
| :482 addon | 能量消耗模块 | `energy_expenditure_plus_10pct` |
| :484 addon | 抗阻优先模块 | `resistance_priority` |
| 计划速度柔韧 4 | 50 米冲刺间歇 | `sprint_50m_intervals` |
| 计划速度柔韧 4 | 动态拉伸 | `dynamic_stretching` |
| 计划速度柔韧 4 | 折返跑 | `shuttle_run` |
| 计划速度柔韧 4 | 坐位体前屈专项 | `sit_and_reach_drill` |
| 补项 1–7 | 快走 / 固定自行车 / 药球核心训练 / 跳跃增强式训练 / 绳梯敏捷 / 本体感觉神经肌肉促进拉伸 / 可选挑战任务 | `brisk_walking` / `stationary_cycling` / `medicine_ball_core` / `plyometric_jump` / `agility_ladder` / `pnf_stretching` / `challenge_task` |

16 + 7 = **23** ✅，落在计划「预估 20–30 个」区间内 ✅。
⚠️ 但 `exercises.yaml:33` 把这 12 项**全部**归给 `:487`，而其中 2 项实际在 `:482`/`:484`；且 `:487` 还点名了「可选挑战任务」，本文件把它算作补项 7 —— 见 M-4。

**视频 URL**：23/23 全部等于 `https://example.invalid/exercise/<自己的 ref>`；不含 `.invalid/` 的 URL **0 条**；**没有任何编造的真实链接** ✅（用户裁定逐字落地）。

**`exercise_equivalence.yaml`**（全部实算，命令见 `review2_probes/p12_data.py`）：

| 判据 | 实测 |
|---|---|
| `version` 非空 | `'1.0'`（字符串；裸 `1.0` 实测解析成 `float`，故加引号是必要的 ✅ 与 `:15-16` 的注释相符） |
| 顶层键 | `['mappings','version','volume_reduction']` 恰好 3 个 ✅ |
| 映射条数 | **10** = 5 个 high × 2 个触发 ✅ |
| 每条键 | 恰好 `from/to/max_impact/when` 4 个 ✅ |
| `volume_reduction` 两系数 | `{bmi_over_30: 0.8, muscle_low_p10: 0.9}`，均 `float`、均在 `(0,1)` ✅ 与计划逐字相符 |
| `when` 取值 | 只有 `bmi_over_30`（5）/ `muscle_low_p10`（5）✅ = spec §7.4 前两个触发；第三个（体脂率异常，`:510`）走 addons，`energy_expenditure_plus_10pct` 实测**既不是 from 也不是 to** ✅（P2-C3 落地） |
| **每条映射都不升冲击** | `from` 全为 `high`、`to` 全为 `low` → 按测试自己的 `IMPACT_DESCENDING` 秩算，**升冲击 offender = 0** ✅ |
| `max_impact` 与 `to` 的真实冲击一致 | 10/10 一致 ✅ |
| 两端都存在 | 10/10 ✅ |
| **每个 `high` 都有 `low` 等价物** | high 5 个（`hiit`/`interval_run`/`plyometric_jump`/`shuttle_run`/`sprint_50m_intervals`），每个在两个触发下都有 `low` 替身，**缺 0** ✅ |
| ⚠️ 头注释 `:33` 的计数 | 「8 个 low 动作里的 **5** 个被用到」→ 实测被用到的 low 动作是 **4** 个（`bodyweight_resistance` / `brisk_walking` / `functional_training` / `stationary_cycling`），而它自己紧接着列出的也正是这 4 个名字 → **见 I-3** |

**⚠️ P10 / P20 未被混淆**（派单 §3-B 特别点的一项）：

- `exercise_equivalence.yaml:62-63`：「spec §7.4 用**肌肉量 < P10**，而 §4.2 / `:384` 的体成分异常判定 `C` 用**肌肉量 < P20**。两个阈值不同、分属两个机制，不得混用」
- 实测 spec `:384` = `C = (体脂率 > 男 20% / 女 28%)  OR  (肌肉量 < 同龄同性别 P20)` ✅
- 实测 spec `:509` = `肌肉量 < 同龄同性别 P10 | 同上，并提高抗阻模块比重` ✅
- YAML 键名 `muscle_low_p10` ✅ 与 §7.4 对齐，**没有**把 P20 混进来 ✅

**spec §14 第 28 项**（P2-A3 要求）：

- 位置 `spec:933`，`git diff --numstat fb5bddb..966eae0 -- Document/…spec.md` = **`1 0`**（一行新增、零删除）✅
- 格式与既有 #18–#27 一致：`| **28** | **事项** | **默认规定** | §7.4 | 影响面 |`，粗体编号 + 5 列 ✅
- **CRLF 保持**：`fb5bddb` blob `82742 B / 973 LF / 0 CRLF`（index 侧 LF）；HEAD blob `84873 B / 974 LF / 0 CRLF`；HEAD 工作树 `85847 B / **974 CRLF** / **0 裸 LF**`。`85847 − 84873 = 974` = 每行恰好多一个 `\r` → **工作树仍是纯 CRLF、且新增了那一行也是 CRLF** ✅
- ⚠️ 该项「影响面」格里的**编号交代已被 `d40f36c` 作废** → 见 I-7

### 1.3 Global Constraints 10 条

| # | 约束 | 实测 | 判定 |
|---|---|---|---|
| 1 | `app/domain/` 无 I/O | AST 扫 `exercises.py` 的 import 面 = **恰好 4 条**：`collections.abc`(level 0) / `dataclasses` / `enum` / `app.domain.indicators`。**实跑守卫自己的函数**：`_is_allowed('collections.abc')=True`、`_is_allowed('dataclasses')=True`、`_is_allowed('enum')=True`、`_is_allowed('app.domain.indicators')=True`；`_is_allowed('sqlalchemy')=False`、`_is_allowed('app.seed')=False`。`templates.py` 只有 `from .exercises import ImpactLevel`（level 1）→ `_absolute('exercises',1,('app','domain','prescription'))='app.domain.prescription.exercises'` → `_is_allowed(...)=True` | ✅ |
| 1 | **allow-list 有没有被偷偷放宽** | `ALLOWED_MODULES` 在 `fb5bddb` / `3ea27cc` / `c21767d` / `HEAD` **四个 rev 上逐字相同** = `frozenset({'dataclasses','enum','collections','collections.abc','numpy','typing'})`（**6 个**）；`ALLOWED_PACKAGE = "app.domain"` 亦未变 | ✅ **一个都没加** |
| 2 | domain 分支覆盖 100% | **全量覆盖率跑不起来**（§0）。**部分实测**：`--cov=app/domain/prescription --cov-branch` 下 `exercises.py **38** stmts / **6** branch`、`templates.py **2** / 0`、`prescription/__init__.py **2** / 0` —— 与账本 Ruling 101/108 记的逐格相符；算术 `406 + 38 + 2 − 5 = 441`、`114 + 6 = 120` 自洽 | ⚠️ **不可复核**（§6-2） |
| 3 | 单一所有者 | `exercise_ref` → `exercises.yaml` 键集（唯一）；每个动作的 `impact_level` → `exercises.yaml`（唯一，`ExerciseSpec` docstring 明写）；`impact_level` **词表** → domain 侧 `ImpactLevel`、db 侧 `Exercise.IMPACT_LEVELS`，**两份 + 一条漂移测试**（`test_exercise_impact_level_vocabulary_agrees_with_the_domain_enum`），这是本包既有「约定 2：枚举取值域两处设防」（`models/__init__.py:16-18`）的既有口径，不是新造的第二所有者；`targets` 取值域 → `ITEM_BUCKET`（`TARGET_DOMAIN` 由它派生，且测试 `:199` 另有字面 `{"endurance","strength","speed_flexibility"}` 兜底，不构成同源）；`volume_reduction` → `exercise_equivalence.yaml`；`IMPACT_RANK` → `exercises.py`（测试侧 `IMPACT_DESCENDING` 刻意独立） | ✅ |
| 4 | 断言两侧不得同源 | 三条新守卫全部字面写死：`test_impact_rank_values_are_pinned_verbatim:512-516` 的 `{HIGH:0, MEDIUM:1, LOW:2}` 三个整数是抄进去的、**不从 `IMPACT_RANK` 读回**；`_PRESCRIPTION_PUBLIC_BASELINE:827-835` 是字面 7 元列表、**且刻意不用 `dir()`**（`:810-816` 给了理由并附亲跑的 `dir(pkg)` 输出）；`test_templates_module_still_reexports_impact_level:146` 的 `["ImpactLevel"]` 是字面量、`:147` 用 `is` 而不是 `==` | ✅ |
| 5 | 散文带口径 | 抽查 40+ 处数字/机制/行号，**绝大多数带 rev 绑定或可 grep 的原文**；`test_prescription_templates.py:100-110` 甚至把「哪个 grep 计数不稳定、故不写进散文」显式交代了。**但仍有 7 组陈述与实测不符** → §3 Important | ⚠️ 部分不达标 |
| 6 | 行号取 shell 口径 | 本报告全部行号由 `read_bytes()` 产出；未用 `Read` | ✅ |
| 7 | PowerShell 纪律 | 全程 `;` 分隔、多行 python 写成 `.py`、写文件走工具/python、未用 heredoc；`$env:PYTHONIOENCODING="utf-8"` | ✅ |
| 8 | 落盘唯一权威是 shell；不得 checkout/switch/merge | **未执行过** `git checkout` / `restore` / `switch` / `merge` / `clean`；取历史版本一律 `git show <rev>:<path>` 并按 `\r\n → \n` 归一化后再比 | ✅ |
| 9 | 禁区四项 | `backend/pe.db` **不存在**；`backend/data/seed/` **0 文件**；`national_standard_2014.csv` = **21412 B / CRLF 0 / `D2C8E539E2FA0029`**（逐字相符）；三个 CLI 的后果性证据均干净 | ✅ |
| 10 | `app/seed/` 冻结 | `git diff --name-status fb5bddb..966eae0 -- backend/app/seed` → **空**（一个字节都没动）；`seed_database` 未被改 | ✅ |

### 1.4 P2 裁定的落地（逐条）

| 裁定 | 实测 | 判定 |
|---|---|---|
| **P2-A1** | 见 §1.1 三行（app/seed 零改动、`sync_exercises` 住址与签名、分区穷尽守卫 + `REFERENCE_TABLES`） | ✅ |
| **P2-A2**（类比是假的） | `refdata_prescription.py:43-49` 与 `prescription.py:37-41` 都改成了「`exercise` 是**参考数据**、同类是 `app/refdata.py`」，**没有**再借用「评分表投影成 DB 表」那个假类比；`test_generate.py:489-493` 用的是「专家维护的知识资产在 DB 里的**投影**」——这里主语是 `exercise`（**真的**被 `sync_exercises` 投影），不是评分表，故不复发 #40 那个形态 | ✅ |
| **P2-A3** | YAML `:51-59` + spec §14 #28 双登记；`EquivalenceTable` docstring `:167-173` 三处都写了「Task 7 不得当 spec 条文引用」；`:56-57` 还显式点名了控制者错误 #40 / 硬规矩 #63 | ✅ |
| **P2-A4** | `TARGET_DOMAIN = frozenset(bucket for bucket in ITEM_BUCKET.values() if bucket is not None)`；实测 `len(set(ITEM_BUCKET.values())) == 4`、含 `None`、`ITEM_BUCKET[ScoredItem.BMI] is None` → True；`TARGET_DOMAIN` = 3 个桶名、无 `None` | ✅（⚠️ 但它引的裁定号错了 → I-5） |
| **P2-A5** | 4 个无 CHECK 列的列宽断言另写在 `test_refdata_prescription.py:531-563`；静态复核：`String(48)≥29`、`String(64)≥12`、`String(256)≥62`、`String(32)≥13`，`impact_level String(8)≥6`；「本表 5 个 `String(n)` 列」实测**恰好 5** | ✅ |
| **P2-A6** | 3 处 `== 15`、函数名 `fifteen`、`git grep fourteen -- backend` 0 命中、按名引用 4 处全对 | ✅（⚠️ 散文里的 3 个行号未同步 → I-4） |
| **P2-A7** | `.gitattributes` 在评审区间内零改动；`.gitattributes:14` = `backend/data/*.yaml  text eol=lf`（逐字）；两个新 YAML 工作树 CRLF = 0 | ✅ |
| **P2-A9** | `load_exercises()` 不缓存（`test:688` 断言 `load_exercises() is not load_exercises()`）、`exercises()` 单例（`:686`），与 `refdata.py` 的 `load_standard()`(:130) + `standard()`(:202) 同构 | ✅ |
| **P2-A10** | `prescription.py:1-42` 的新 docstring 逐条更正了那 4 处：`training_package` 不是表（引计划 `:568`/`:569`）、`prescription` 归 Task 9（引计划 `:524`）、`prescription_override` 计划里没有（引计划 `:491`/`:700`）、补上 `exercise` 与四张表的归属表 | ✅ 4 处引文我逐条对过 `fb5bddb` 的计划原文，**全部逐字相符** |
| **P2-B1 / B2 / B3 / C1 / C2 / C3** | B1：`{__init__,templates}.py` 由 Task 2 建、`templates.py` 只放 `ImpactLevel`（现已迁走、只剩 re-export）；B2：见 §1.1；B3：`refdata_prescription.py:3-14` 的分段表；C1：见 §1.1；C2：测试名已改；C3：`when` 只有两个取值 | ✅ |
| **P2-D4** | 实跑守卫自己的扫描函数：`_py_files('pipeline')=7`、`('db')=11`、`('domain')=9`，合计 **27**（= 24 + 3）；`_domain_files()` = **9**；两条架构守卫 **6 passed**（在我的 10 passed 里） | ✅ 预测方向正确 |
| **Ruling 96**（搬迁） | AST 扫 `exercises.py` 顶层 = **恰好 7 个**：`ImpactLevel`(:44) / `TARGET_DOMAIN`(:79) / `EQUIVALENCE_TRIGGERS`(:87) / `IMPACT_RANK`(:103) / `ExerciseSpec`(:111) / `EquivalenceMapping`(:140) / `EquivalenceTable`(:160)，与裁定清单逐字相符；`refdata_prescription.py` 顶层**已无任何值对象/词表定义**（只剩 2 个文件名常量、3 个私有校验常量、2 个缓存、7 个函数）；`templates.py` 顶层只剩 `__all__`(:39) + 一句 re-export(:37) | ✅ **搬迁完整** |
| **Ruling 96 的历史陈述** | `git show 3ea27cc:backend/app/refdata_prescription.py` → `_IMPACT_RANK` 定义在 **:96**、共 5 处命中；`c21767d`/HEAD 上该文件 `_IMPACT_RANK` = **0** 处、`IMPACT_RANK` = 1 处（import） | ✅「Ruling 96 之前它叫 `_IMPACT_RANK`、住在 `app.refdata_prescription`」**为真** |
| **Ruling 97** | `models/__init__.py:84-88` 写明「Plan 02 新加的表类刻意不进 `__all__`」；`__all__` 实测 **14** 个名字（Plan 01 的 14 张表），**不含 `Exercise`** | ✅ |

---

## 2. 结论

# **Approved with findings**

**理由**：Task 2 的**行为面全部合格**——数据正确（23 个动作 / 10 条映射 / 全部安全属性实算成立）、
spec §4.4 的六项一一对应、视频 URL 全是 `.invalid` 占位符（无编造链接）、P2-A3 的「无 spec 出处」
双登记到位、P10/P20 未被混淆、Global Constraints #1/#3/#4/#9/#10 与 P2-A1…A10 / B1…B3 / C1…C3 / D1…D4
以及 Ruling 96/97 的裁定**逐条落地**，两个 YAML 的指纹与测试里钉的常量逐字相符，`.gitattributes` 与
`app/seed/` 一个字节未动。三条新守卫的期望值全部字面写死、且刻意避开 `dir()` 那条同源陷阱。
fr2 对两份架构守卫的散文修正**质量很高**：我实跑了它印在散文里的每一条取证命令与每一个折算值，
**逐字相符**（见 §5）。

**但**：源码散文里查出 **7 组与实测不符的陈述**（共 **12 个物理位置**），其中 3 组是**多份副本**
（硬规矩 #51 要求逐份修）。这正是本项目唯一反复出现的错误类，也是 Task 1 收尾评审在同一位置查出
2 Important + 6 Minor 的同一位置。**没有一条会让守卫假绿、也没有一条破坏安全属性**，故不判 Needs work；
但其中 I-2 会让读者**误以为安全守卫覆盖了生产侧的秩**，I-4/I-6/I-7 会**主动误导 Task 3 / Task 12**，
建议在派 Task 3 之前一并清掉（I-3/I-6 改的是被指纹钉住的 YAML，须同步更新 `EXERCISES_FINGERPRINT` /
`EQUIVALENCE_FINGERPRINT`；I-7 改的是 `Document/`，须另开授权）。

**findings 计数：Critical 0 / Important 7 / Minor 10。**

---

## 3. Findings

### 3.1 Critical（0 条）

无。逐条排查过三类可能：
① **假绿**：三条新守卫的期望值都字面写死、且支 5 用 AST 而不是 `dir()`，支 4 还先断言了「所有者侧取到的不是 `None`」以防 `None is None` 退化成恒真（`test_refdata_prescription.py:891-900`）——**没有假绿口子**；
② **安全属性被破坏**：10 条映射实算 0 升冲击、5 个 high 全部有 low 替身、`max_impact` 与真实冲击 10/10 一致——**安全属性成立**；
③ **错误行为**：`load_exercises` / `load_equivalence` / `sync_exercises` 的校验分支我逐条读过，9 + 11 个 parametrize 拒绝用例的期望 `needle` 与被引的报错文本逐条对得上——**未发现行为缺陷**。

### 3.2 Important（7 条 = 印在源码里的陈述与实测不符）

---

#### I-1 `str(ImpactLevel.HIGH)` 的**字符数印错**（16 不是 19），且**「SQLite 会按 `str()` 存」这个机制不成立** — 2 份副本

**位置与原文**

- `backend/app/domain/prescription/exercises.py:49-51`
  > 漏写一处的失效形态是**静默的**：SQLite 会把枚举对象按 ``str()`` 存成 ``"ImpactLevel.HIGH"``（**19 字符**，还撑破 ``String(8)``——SQLite 不强制长度，故写侧不报错，换严格长度的后端才截断，硬规矩 #18 的那个失效形态）。
- `backend/tests/domain/test_prescription_templates.py:62-65`
  > 不继承 ``str`` 的话，ORM 侧就得处处写 ``.value``，而漏写一处的失效形态是**静默的**：SQLite 会把枚举对象按 ``str()`` 存成 ``"ImpactLevel.HIGH"``（**19 字符**，还会撑破 ``String(8)``…）

**实测**（`review2_probes/p11_facts.py`，E1.3 / E1.4；纯 Python + 标准库 `sqlite3`，不经 sqlalchemy）

```
str(ImpactLevel.HIGH) = 'ImpactLevel.HIGH'  len = 16
len('ImpactLevel.HIGH') literal count = 16
repr = <ImpactLevel.HIGH: 'high'>   format = ImpactLevel.HIGH

# 裸 sqlite3：CREATE TABLE t (lv VARCHAR(8)); INSERT INTO t (lv) VALUES (?)  绑定 ImpactLevel.HIGH
stored value = 'high'   typeof = text   sqlite length() = 4
# 对照：显式绑定 str(ImpactLevel.HIGH)
('ImpactLevel.HIGH', 16)
```

**判读**：两处都错。
① **计数错**：`"ImpactLevel.HIGH"` 是 **16** 字符（`ImpactLevel` 11 + `.` 1 + `HIGH` 4），不是 19。`repr()` 是 27、`format()` 是 16，**没有任何一种口径给得出 19**。
② **机制错**（硬规矩 #29/#63 的正靶心）：`ImpactLevel` 是 `str` 子类，**它自己的字符数据就是 `"high"`**；DBAPI 传的是字符数据、不是 `str()` 的返回值，故落库是 `'high'`（`typeof=text`、`length()=4`），**既不撑破 `String(8)`、也不会在严格长度后端被截断**。只有显式写 `str(x)` 才得到 16 字符那一版。
③ 补一层：生产路径**根本不会把枚举交给 ORM**——`refdata_prescription.py:398` 写的是 `spec.impact_level.value`。
④ **不可复核的部分**：sqlalchemy 的 `String.bind_processor` 在 SQLite 方言下是否额外做 `str()` 强转，本机跑不了（§0）。但 SQLite 方言 `supports_unicode_binds` 为真时该 processor 返回 `None`、值原样下传，与裸 `sqlite3` 的结果一致；且无论哪一种，**「19 字符」都是错的**。

**建议修法**（两份都要改，硬规矩 #51）：把这句改成实测得到的形态，例如
「漏写 `.value` 的失效形态取决于后端与方言：本仓实测（裸 `sqlite3`，绑定 `ImpactLevel.HIGH`）落库是 `'high'`（`typeof=text`、`length()=4`），**因为 `str` 子类的字符数据就是值本身**；`str(x)` 才给出 `'ImpactLevel.HIGH'`（**16** 字符，会撑破 `String(8)`，而 SQLite 不强制长度、换严格长度的后端才截断）。生产路径一律写 `.value`（`refdata_prescription.py:398`），故这条失效今天不可达。」
若不想承担「不可达」这句话的举证责任，最省的修法是**删掉这个具体机制、只留「继承 `str` 让 `ImpactLevel.HIGH == "high"` 直接成立」**（那半句实测为真）。

---

#### I-2 「改坏 `IMPACT_RANK` 也会让 `test_equivalence_never_maps_to_a_higher_impact_level` 红」**不成立** — 3 份副本 + 1 处自相矛盾

**位置与原文**

- `backend/app/domain/prescription/exercises.py:55-59`
  > 冲击序由消费方显式声明，今天有两份、刻意不同源（硬规矩 #35）：生产侧是**本模块**的 :data:`IMPACT_RANK`…测试侧 ``tests/test_refdata_prescription.py`` 的 ``IMPACT_DESCENDING``。**改坏任何一份都会让 ``test_equivalence_never_maps_to_a_higher_impact_level`` 变红。**
- `backend/tests/test_refdata_prescription.py:85-86`
  > 两侧不同源，**改坏任何一侧都会让** :func:`test_equivalence_never_maps_to_a_higher_impact_level` **红**。
- `backend/tests/test_refdata_prescription.py:308-309`
  > 两份刻意不同源，**改坏任何一份本条都红**（硬规矩 #35）。
- 而**同一个文件** `exercises.py:94-96` 写的是**正确**版本：
  > 改坏任何一份，``test_equivalence_never_maps_to_a_higher_impact_level`` **与** :func:`test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable` **之一**会红。

**实测**（`review2_probes/p13_mut.py`，E4.3 = AST 扫那 4 条测试各自引用了哪个名字）

```
test_equivalence_never_maps_to_a_higher_impact_level                     IMPACT_RANK=False IMPACT_DESCENDING=True
test_every_high_impact_exercise_has_a_low_substitute                     IMPACT_RANK=False IMPACT_DESCENDING=False
test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable  IMPACT_RANK=False IMPACT_DESCENDING=False
test_impact_rank_values_are_pinned_verbatim                              IMPACT_RANK=True  IMPACT_DESCENDING=True
```

`test_equivalence_never_maps_to_a_higher_impact_level`（`:315-334`）的秩是
`rank = {value: index for index, value in enumerate(IMPACT_DESCENDING)}`（`:317`）——**它从头到尾没有读过 `IMPACT_RANK`**，
`load_exercises()` / `load_equivalence()` 也不碰它。故**改坏生产侧 `IMPACT_RANK` 时这一条恒绿**。

**旁证（账本自己的实测，与我的静态结论一致）**：Ruling 108 记 M-B（`IMPACT_RANK` 的 `HIGH:0 ↔ LOW:2` 对调）→ **`1 failed, 527 passed`，红在 `:434`**，而 `:434` 正是 `test_lookup_honours_...` 的 `def` 行；fr2 的 `test_impact_rank_values_are_pinned_verbatim` docstring `:481-482` 也写「M-B 实测只让**其中 1 条**红」。

**我自己的复现**（E4.2，用改过的秩字典重跑 `lookup` 的判据）：

```
REAL   real-table asserts ok=True ; synthetic asserts ok=True
M-A1   real-table asserts ok=False ; synthetic asserts ok=False
M-A2   real-table asserts ok=True ; synthetic asserts ok=False
```

即两个秩变异都只打 `test_lookup_...` 与新加的 `test_impact_rank_values_...`，**打不到**「不升冲击」那一条。

**为什么这条要紧**（不只是措辞）：它是一条**守卫归属**陈述。照它读，会以为 spec §7.4 那条核心安全属性
（不升冲击）同时看着生产侧的秩；实际它只看数据侧。fr2 加的 `test_impact_rank_values_are_pinned_verbatim`
补上了这个缺口——**但三处旧散文没跟着更正**，于是账面上仍然印着一个假的覆盖关系。同时它也是
**硬规矩 #56（判定要标主语）的违反**：「改坏任何一份」把两份词表混成一个主语。

**建议修法**（三份都改，硬规矩 #51）：统一成 `exercises.py:94-96` 那个已经正确的口径，并标主语：
「改坏**测试侧** `IMPACT_DESCENDING` → `test_equivalence_never_maps_to_a_higher_impact_level` 红；
改坏**生产侧** `IMPACT_RANK` → `test_impact_rank_values_are_pinned_verbatim`（支 1/2/3/4）与
`test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable` 红，**而『不升冲击』那一条不红**
（它只读测试侧那份，AST 实测 `IMPACT_RANK` 在它的函数体里 0 命中）。」

---

#### I-3 `exercise_equivalence.yaml:33` 的「8 个 low 动作里的 **5** 个被用到」是 **4**，且与它自己列的 4 个名字自相矛盾

**原文**（`backend/data/exercise_equivalence.yaml:32-34`）
> 每条的 `max_impact` 都是 `low`，且 `to` 的真实冲击也都是 `low`（8 个 low 动作里的 **5** 个被用到：stationary_cycling / brisk_walking / bodyweight_resistance / functional_training，其中 stationary_cycling 被 4 条复用）。

**实测**（`review2_probes/p12_data.py`，E2.3）
```
low refs (8) = ['band_resistance','bodyweight_resistance','brisk_walking','dynamic_stretching',
                'functional_training','pnf_stretching','sit_and_reach_drill','stationary_cycling']
distinct 'to' (4): ['bodyweight_resistance','brisk_walking','functional_training','stationary_cycling']
low refs used as a target (4) = 同上
'to' reuse counts = {'stationary_cycling': 4, 'brisk_walking': 2, 'bodyweight_resistance': 2, 'functional_training': 2}
```

**判读**：被用到的 low 动作是 **4** 个（8 − 4 未用：`band_resistance` / `dynamic_stretching` / `pnf_stretching` / `sit_and_reach_drill`）。
括号里列出的名字也**正好是 4 个**——即这一句自己就自相矛盾。同句的「stationary_cycling 被 **4** 条复用」**为真** ✓（4 条：`interval_run`×2 + `sprint_50m_intervals`×2）。
**这是一个纯计数错**，属硬规矩 #54/#66 的正靶心。

⚠️ **修改代价**：这一行在被指纹钉住的文件里，改它必须同步更新
`test_refdata_prescription.py:72` 的 `EQUIVALENCE_FINGERPRINT`（现值 `0FFB881574AC04F3`）。

**建议修法**：`5 个` → `4 个`，并可顺手把未被用到的 4 个点名（「`band_resistance` / `dynamic_stretching` / `pnf_stretching` / `sit_and_reach_drill` 今天不是任何映射的落点」），这样下一个人加映射时有据可依。

---

#### I-4 `tests/db/test_models.py` 三处 `==` 的**行号在改它们的那一笔里就过期了** — 2 份副本

**位置与原文**

- `backend/tests/db/test_models.py:35-36`（在 `test_all_fifteen_tables_created` 自己的注释里）
  > 每个 Task 只改自己那一步，并同步改函数名里的英文数词与本文件 **``:163`` / ``:228`` / ``:472``** 的三处 ``==``
- `backend/app/db/models/prescription.py:20-21`
  > **必须同步改那道守卫的期望集合、``== 15`` 的三处断言与函数名里的「fifteen」**（``tests/db/test_models.py`` ``:24`` / **``:163``** / **``:228``** / **``:472``**）

**实测**
```
$ python -c "<grep '== 15\\b' in tests/db/test_models.py>"
  :169| assert len(tables) == 15, "守卫的覆盖面必须先被确认是这 15 张表"
  :236| assert len(tables) == 15, "守卫的覆盖面必须先被确认是这 15 张表"
  :494| assert len(Base.metadata.tables) == 15

$ <HEAD 上 :163 / :228 / :472 分别是什么>
  :163| ``integer 0``、读回 ``int 0``，审计记录里的「原值 65.0 kg」变成「原值 65」。   ← docstring 散文
  :228| 在本项目里专指「指向 ``daily_sync_run`` 的外键」，也就是 ``delete_by_batch`` 可据以   ← docstring 散文
  :472| f"{sorted(_MODELS_SUBMODULES & set(_MODELS_PUBLIC_BASELINE))}"                  ← 另一条测试的 f-string

$ <fb5bddb（改前）上同样三个行号>
  :163| assert len(tables) == 14, ...      :228| assert len(tables) == 14, ...      :472| assert len(Base.metadata.tables) == 14
```

**判读**：`:163` / `:228` / `:472` 是 **`fb5bddb` 上 `== 14` 的位置**（P2-A6 亲验时是对的），
Task 2 自己把它们改成 `== 15` 并因此推到了 **`:169` / `:236` / `:494`**，而**两处散文都没跟着改**。
`prescription.py:21` 的 `:24` 那一处（函数名）**是对的** ✓。
这与 fr2 刚修完的 CE-7（`__init__.py:74` → `:82`）是**完全同一个失效形态**，
而 fr2 的修法（改用**可 grep 的原文**、并显式写「不写裸行号」）恰恰是这里该用的。

**建议修法**：两处都改成 fr2 在两份架构守卫里已经确立的口径——**不写裸行号，写可 grep 的原文**：
「同步改本文件里三处 `assert len(tables) == 15` / `assert len(Base.metadata.tables) == 15`
（`git grep -n "== 15" -- backend/tests/db/test_models.py` 现命中 3 处）与函数名里的英文数词」。
若一定要留行号，必须绑 commit（`在 966eae0 上是 :169 / :236 / :494`）。

---

#### I-5 「BMI 不归任何短板桶」引的裁定号错了：**Plan 01 Ruling 19 讲的不是这件事** — 2 份副本

**位置与原文**

- `backend/app/domain/prescription/exercises.py:74-76`
  > ⚠️ **不是 ``set(ITEM_BUCKET.values())``**（Plan02 账本 P2-A4）：那个集合有 **4** 个元素、含 ``None``（``ITEM_BUCKET[ScoredItem.BMI] is None``，因为 BMI 天然不属于任何短板桶，**Plan01 Ruling 19 的口径**）
- `backend/tests/test_refdata_prescription.py:198`
  > `assert None in raw_values, "BMI 不归桶（**Plan01 Ruling 19**），故 None 必在其中"`

**实测**（`review2_probes/p18_rulings.py`，J1/J2/J3/J5 + `git grep`）
```
Plan01 账本（805 520 B / 4856 行）里 "Ruling 19" 只有 1 处定义：
  :170| **Ruling 19 — `raw_from_score` 对非单调序列抛 `ValueError`，不得返回哨兵。**
  :171| 评审实测 `raw_from_score(T, BMI, 80, MALE, G) = 0.0`（哨兵泄漏）…
  :172| 裁定：检测 score 序列沿 raw 升序是否单调，非单调（即 BMI）→ 抛 `ValueError`…

"BMI 不参与短板判定与桶化" 这个口径实际住在：
  :133| 裁定接受，依据：① BMI 按 spec §4.2 **不参与短板判定与桶化**，只进国标总分；…
        （该行属于 :115 的 **Ruling 17** 之下的「关切 1（BMI 非单调区间映射）」）
  :1390/:1395| …`WEAKNESS_ITEMS` 天然排除 BMI…

本仓既有的 "Ruling 19" 用法（全部指 raw_from_score 那件事，用法正确）：
  backend/app/domain/percentile.py:131       …拒绝 BMI 的判据**同一条**（Ruling 19：…
  backend/data/README_national_standard.md:129  **`raw_from_score` 对 BMI 直接抛 `ValueError`（Ruling 19）**
  backend/tests/domain/test_indicators.py:268   # Ruling 19：BMI 两头 80、中间 100，非单调…
```
Plan 02 账本自己的 Ruling 19 是「开工时工作树是脏的」，也不是这件事。

**判读**：**引用号错**（硬规矩 #55 的正靶心：引用编号前先 grep 确认）。
被引的那条裁定讲的是**反查函数的非单调护栏**，而这里要引的是**「BMI 不进短板桶」**。
两者都跟 BMI 有关，所以直觉审查过得去——**正是硬规矩 #63 说的「借一个真实存在的机制、套到不成立的对象上」的形态**。
**源头在账本**：P2-A4（`progress.md:999`）自己就写着「Plan 01 Ruling 19 的口径」，实现者照抄进了两份源码 → 记控制者错误 CE-7（§4）。

**建议修法**（两份都改）：把「Plan01 Ruling 19 的口径」换成
「**spec §4.2 的口径；Plan01 账本 `:133`（Ruling 17 关切 1）明写「BMI 按 spec §4.2 不参与短板判定与桶化」**」，
或直接引可 grep 的原文（`ITEM_BUCKET[ScoredItem.BMI] is None`，实测为真）。
**顺手把账本 P2-A4 那句一起勘误**，否则 Task 3/4 会第三次抄它。

---

#### I-6 `exercises.yaml:21-22` 的「预留为 **#29**」已被 `d40f36c` 作废，今天是 **#30**

**原文**（`backend/data/exercises.yaml:20-22`）
> ⚠️ 这一条**尚未登记进 spec §14**：本轮只被授权追加第 28 项（volume_reduction 系数），而计划 Task 12 Step 3 已把「动作库的视频源」预留为 **#29** —— 见 task-2-report.md 的「关切与未尽事项」。

**实测**
```
$ git log --oneline fb5bddb..966eae0
  966eae0 … c21767d … 4386ee2 … d40f36c docs: Ruling 92/93 重排 spec §14 编号（Task 2 已占 #28，
                                        Task 12 的 7 项去重后为 #29-#34 共 6 项，总数仍 34）… 3ea27cc …

$ <HEAD 计划正文>
  :682| Step 3: spec 勘误与 §14 补项（本 Task 追加 **6 项，#29–#34**）
  :688| …**#29** 18 套模板的审校状态；**#30** 动作库的视频源（占位 `.invalid` URL；⚠️ Task 2 已把它
        写进 `exercises.yaml` 的头注释，本项是把它正式登记进 §14）；**#31** …

$ git show fb5bddb:Document/…计划02….md | 第 685 行
  :685| - §14 补：**#28** 18 套模板的审校状态；**#29** 动作库的视频源（占位 `.invalid` URL）；…
```

**判读**：这句话在**写下来的那一刻（`3ea27cc`）是真的** ✓，但**紧接着的 `d40f36c` 就把它作废了**，
而 `c21767d` / `966eae0` 都没动 `backend/data/`（改动面纪律），于是它一直留在 HEAD 上。
账本 Ruling 93 自己就写了「视频源的 §14 登记归 Task 12（**重排后是 #30**）」——**正确答案在账本里，YAML 没跟上**。
这是硬规矩 #66（改一处同类计数，必须 grep 出全部同类逐个更新）在**跨文件方向**上的一次落空：
`d40f36c` 改了计划正文，没改引用它的 YAML。

⚠️ **修改代价**：改它要同步 `test_refdata_prescription.py:69` 的 `EXERCISES_FINGERPRINT`（现值 `A6A000F58815FCBB`）。

**建议修法**：`预留为 #29` → `预留为 #30（`d40f36c` 重排后；原 #29 已被 #28 顶下来一位）`，
或按 I-4 的建议改成可 grep 的原文（「计划 Task 12 Step 3 的 §14 补项清单里那一条『动作库的视频源』」）+ 绑 commit。

---

#### I-7 spec §14 第 28 项「影响面」格里的**编号交代已被 `d40f36c` 执行掉，且它开的处方与实际结果不符**

**原文**（`Document/2026-09-28-体育闭环原型-设计spec.md:933`，第 28 项最后一格）
> ⚠️ **编号冲突待 Task 12 处理**：计划 02 的 Task 12 Step 3（计划 `:681` 与 `:685`）已把 **#28** 预留给「18 套模板的审校状态」、把 **#32** 预留给与本项**同一主题**的「§7.4 的跑量下调系数与『提高抗阻比重』的处置」。本项因「值在这一刻被写死」提前到 Task 2 登记（Plan02 账本 P2-A3 的裁定），故 Task 12 须把它那 7 项**整体后移为 #29–#35**，并**删掉与本项重复的那一条**（原 #32），否则同一件事会在 §14 里出现两次。

**实测**
```
$ git show d40f36c --stat   → 只改 Document/…计划02….md
$ <HEAD 计划正文>
  :682| Step 3: spec 勘误与 §14 补项（本 Task 追加 **6 项，#29–#34**）
  :684| ⚠️ **P2-A3 的后续更正（Task 2 实现后）**：原文这里是「7 项，#28–#34」。**#28 已被 Task 2 用掉**…
        故本 Task 的清单整体前移一位、并删掉重复的那项：原 #28→**#29**、原 #29→**#30**、原 #30→**#31**、
        原 #31→**#32**、~~原 #32~~（**删除**，已由 Task 2 的 #28 覆盖）、原 #33→**#33**、原 #34→**#34**。
        **7 项 − 1 项重复 = 6 项**，而 §14 总数仍是 `27 + 1（Task 2）+ 6（本 Task）= **34**`
  :707| spec §14 从 27 项扩到 **34 项**
$ git diff --numstat fb5bddb..966eae0 -- Document/…spec.md   → "1 0"（spec 只被加过那一行，d40f36c 没碰它）
```

**判读**：三层问题。
① **时态过期**：「编号冲突**待** Task 12 处理」——冲突已经在 `d40f36c`（Task 2 的评审区间**之内**）由控制者处理完了。
② **处方与结果不符**：spec 开的处方是「整体后移为 **#29–#35**（7 个号）再删掉重复的一条」；照字面执行会留下 6 项但**号段到 #35**（并留一个空洞）。实际执行的是**去重后连续编号 #29–#34（6 项）**，总数 `27+1+6=34`。两个结果不一样。
③ **它引的计划行号也过期了**：「计划 `:681` 与 `:685`」是 `fb5bddb` 的位置，HEAD 上是 `:682` 与 `:688`。

**为什么这条不只是排版**：spec §14 是**交给项目负责人（邹红老师）裁决**的清单，
它印着一个**已经被执行、且执行结果与它写的不同**的指令。Task 12 若照 spec 这一格办事，
会把已经正确的 `:682/:688` 再改一遍、真的造出一个 #35。

**建议修法**：把那一格改成**既成事实的陈述**（并绑 commit）：
「⚠️ **编号冲突已由计划 02 的 `d40f36c` 处理完毕**：Task 12 的清单去重后为 **6 项、#29–#34**
（原 #28→#29、#29→#30、#30→#31、#31→#32、~~原 #32~~ 删除（已由本项覆盖）、#33→#33、#34→#34），
§14 总数仍为 `27 + 1 + 6 = **34**`。见计划 `:682`/`:684`/`:688`/`:707`（行号绑 HEAD `7296793`）。」
⚠️ 这需要**改 `Document/`**，而 Task 2 的派单只授权追加 §14 第 28 项一行 → **须由控制者另开授权**（或并入 Task 12 的 Step 3）。

---

### 3.3 Minor（10 条）

| # | 位置 | 原文 / 问题 | 实测 | 建议 |
|---|---|---|---|---|
| **M-1** | `backend/tests/test_refdata_prescription.py:599` | 「这条与 :func:`test_impact_level_vocabulary_agrees_with_the_domain_enum` 分工不同」 | `git grep -n test_impact_level_vocabulary_agrees_with_the_domain_enum -- backend` → **只有这 1 处命中，全仓没有这个函数**；真名是 `test_exercise_impact_level_vocabulary_agrees_with_the_domain_enum`（`:566`，且 `prescription.py:83` 引的是**正确**的全名） | 补上漏掉的 `exercise_` 前缀。**这是本节里唯一一处「跨模块交叉引用指向不存在的对象」** |
| **M-2** | `backend/app/refdata_prescription.py:356` | 「本 Task 的**四个函数**里计划只点了 `load_exercises` / `exercises` / `load_equivalence` 三个；补这一个是为了对称」 | 本模块的公有函数是 **5** 个：`load_exercises`(:178) / `exercises`(:220) / `load_equivalence`(:282) / `equivalence`(:353) / **`sync_exercises`(:366)**。「四个」只在「加载器四件套」这个未言明的口径下成立 | 改成「本 Task 的**四个加载器函数**里…」或「加载侧的四个函数里…」——把主语补上（硬规矩 #56 的同一条纪律） |
| **M-3** | `backend/app/refdata_prescription.py:374-375` | 「**本函数 flush 但不 commit**：事务边界由调用方掌握（**与 `app.db.repo.upsert` 同一口径**）」 | `repo.py:39` 逐字是「本函数**既不 commit 也不 flush**：事务边界由调用方掌握」。即 `upsert` 与 `sync_exercises` 只在「不 commit」这半句同口径，**在 flush 上恰好相反** | 收紧成「（与 `upsert` 同样**不 commit**；`upsert` 自己连 flush 也不做，见 `repo.py:39`，故本函数在循环外统一 flush 一次）」 |
| **M-4** | `backend/data/exercises.yaml:33-37` | 「骨架 = spec §7.2 **:487** 点名的 **12** 项（… 能量消耗模块、抗阻优先模块）+ 速度柔韧类 4 项 = 16，再补 7 项 = 23」 | spec `:487` 那一行实际点名的是：间歇跑/复合循环/能量消耗模块/持续跑/台阶训练/自重/弹力带抗阻/HIIT/兴趣球类/定向越野/功能性训练/**可选挑战任务** —— 即**「抗阻优先模块」在 `:484`、「可选挑战任务」在 `:487`**；而本文件把「可选挑战任务」算作**补项 7**（`:256`）。**数字 12 与 16 与 23 都对，但「12 项全部出自 `:487`」这个归属不对** | 改成「spec §7.2 `:487` 与两个 addon 模块名（`:482`/`:484`）合计点名的 12 项」；并在补项 7 那段说明「`:487` 也点了『可选挑战任务』，本文件把它算作补项是因为它此前没有 ref」 |
| **M-5** | `backend/tests/seed/test_generate.py:506` | 「`seed_database` 越界写它也不会红，**因为那条守卫只遍历 `DATA_TABLES`**」 | 同一文件 `:567` 实测是 `for table in DATA_TABLES + REFERENCE_TABLES:`，且 `:541-542` 明写「Plan 02 Task 2 把下面『必须为 0』那一圈的遍历对象从 `DATA_TABLES` 扩成 `DATA_TABLES + REFERENCE_TABLES`」；本 docstring 自己的 `:510` 也说「认领进 `DATA_TABLES` / `REFERENCE_TABLES` 的表…」。**结论仍成立**（不在任何分区里的表两条守卫都遍历不到），但**给出的理由在 HEAD 上不准确** | 改成「因为两条守卫都只遍历**已被分区认领**的表（`DATA_TABLES + REFERENCE_TABLES` 与 `ORGANISATION_TABLES`）」；若要保留历史口径，标时点「Task 2 之前它只遍历 `DATA_TABLES`」 |
| **M-6** | `backend/data/exercises.yaml:91` 与 `:155` | 「快走把冲击峰值**从跑的 2–3 倍体重降到约 1.2 倍**」/「反复落地 = 反复 **2–3 倍体重**冲击」 | 两个运动生理学数值**没有任何出处、单位口径或「不被守卫」标注**。硬规矩 #19 要求「每个数字都要能指到产生它的那条命令；尺寸/时长/速率必须带单位与进制」，写不出来的要标「历史实测，不被守卫」 | 加一句来源（指导文件/运动处方规范的章节），或显式标注「**工程估计，无出处，不被任何测试守卫**」——与 `volume_reduction` 两个系数的处置口径保持一致（那两个数是**做了**登记的） |
| **M-7** | `backend/app/domain/prescription/exercises.py:55` | 「冲击序由消费方显式声明，**今天有两份**、刻意不同源」 | fr2 之后**字面写下这个序的地方有三处**：`IMPACT_RANK`（生产）、`IMPACT_DESCENDING`（测试侧元组）、`test_impact_rank_values_are_pinned_verbatim:512-516` 的 `{HIGH:0, MEDIUM:1, LOW:2}` 字面字典。fr2 的 `backend/app/**` 是 0 字节改动，故这句来不及更新 | 「两份」→「**两个消费方**各一份（生产 `IMPACT_RANK` / 测试 `IMPACT_DESCENDING`），另有一处**字面期望值**在 `test_impact_rank_values_are_pinned_verbatim`」——把「声明者」与「期望值」分开数 |
| **M-8** | `backend/data/exercises.yaml:217-241` | 分节标题 `:218` 是「**绿层**兴趣 / 综合，与两个 addon 模块」，而 `hiit`（`:236`）自己的注释 `:235` 写「spec §7.2 :487『体脂偏高附加 5min HIIT』（**黄层**）」 | 实测 spec `:487`：HIIT 确属**黄层**；`energy_expenditure_plus_10pct` 属**红层**（`:482` 注释「红层 +10% 能量消耗」）。即这一节里 5 个条目分属红/黄/绿三层，而节标题只说「绿层」 | 节标题改成「兴趣 / 综合与两个 addon 模块（跨红/黄/绿三层，逐条见各自注释）」 |
| **M-9** | `backend/data/exercises.yaml:259-261` | 「变异验收 ② 用的正是这个 ref：删掉它，全仓**只有**指纹测试会红——因为**没有任何一条映射或断言依赖它**」 | 「只有指纹会红」**为真** ✓（实测 `challenge_task` 不在任何映射里；`lookup` 只查等价表、不查动作库，故 `test_refdata_prescription.py:449` 的 `assert table.lookup("challenge_task", LOW) is None` 删掉该 ref 后**仍然绿**）。但「没有任何一条**断言**依赖它」在字面上不成立：`:449` 就把这个 ref **硬编码**进了断言 | 改成「没有任何一条映射依赖它，也没有任何一条断言会**因为它消失**而变红（`test_refdata_prescription.py:449` 硬编码了它当『无映射的 ref』探针，删掉它那条仍然绿、只是探针语义变弱）」 |
| **M-10** | `backend/app/domain/prescription/exercises.py:191-192` | 「故专家可以通过调整书写顺序来↵表达偏好」 | 换行点落在「来 / 表达」之间，读起来像两句；纯排版 | 重排该行的折行点 |

---

## 4. 我发现的控制者错误（账本 / 派单 / 计划文档 / 简报 / 评审包）

**按事实判，不照顾控制者。** 逐条注明成立 / 不成立 / 歧义 + 证据。
⚠️ 同时按账本 Ruling 45/51/65 的纪律：**把不成立的指控认下来和把成立的辩掉是同一种失职**，故 §4.2 也逐条列出我核过但**不成立**的怀疑。

### 4.1 成立（7 条）

| # | 位置 | 原文 | 实测 | 严重度 |
|---|---|---|---|---|
| **CE-1** | **派单 §3-A** | 「`backend/app/refdata_prescription.py`（**约 507 行**）」 | 逐 rev 数 LF：`3ea27cc` **507** / `c21767d` **406** / `966eae0` **406** / HEAD **406**。**507 是 Ruling 96 搬迁之前的值**，而派单自己 §0 钉的代码基线是 `966eae0` | 成立（Minor，过期状态） |
| **CE-2** | **派单 §3-A** | 「`backend/app/domain/prescription/{__init__,templates,exercises}.py`（**12 / 39 / 200 行**）」 | `__init__.py`：`3ea27cc` **12** / `c21767d` **37** / HEAD **37**。`templates.py`：`3ea27cc` **45** / HEAD **39** ✓。`exercises.py`：HEAD **200** ✓。→ **这个三元组混了两个 rev**：12 取自 `3ea27cc`，39 与 200 取自 HEAD；在**任何一个** rev 上都不成立 | 成立（Minor，同一句里 rev 不一致） |
| **CE-3** | **派单 §3-A** | 「`backend/tests/test_refdata_prescription.py`（**约 1050 行**）」 | 逐 rev 数 LF：`3ea27cc` **722** / `c21767d` **727** / `966eae0` **921** / HEAD **921**。**1050 在 Task 2 全链上没有任何一个 rev 对得上**（不是过期值，是无出处的数） | 成立（Important：这是硬规矩 #61 的正靶心——派单里的数量必须 shell 亲验） |
| **CE-4** | **派单 §1** + **评审包 `:68`** | 派单：「**禁区命中检查**（`backend/data`、`backend/app/seed`、评分表 CSV，**三者都应为空**）」；评审包标题：「## 禁区命中（**三者都必须为空**）」 | 评审包 `:71-76` 自己的输出是<br>`-- backend/data:`<br>`backend/data/exercise_equivalence.yaml`<br>`backend/data/exercises.yaml`<br>`-- backend/app/seed:` `(none)`<br>`-- …csv:` `(none)`<br>→ **第一项有 2 条命中，与它自己的标题直接矛盾**。根因是**口径取错**：Global Constraint #9 的禁区是 `backend/data/seed/`（0 文件）与那份 CSV，**不是整个 `backend/data/`**；而 P2-D2 已明确裁定「两个新 YAML 放 `backend/data/` **根**，不是 `data/seed/`，**无冲突**」。**实质禁区未被侵犯**（`data/seed/` 0 文件 ✓、CSV 指纹 ✓、`backend/data` 里既有的 3 个文件在 `fb5bddb..966eae0` 的 name-status 里 **0 命中** ✓） | 成立（Important：一个自相矛盾的验收判据；照标题读会以为 Task 2 踩了禁区，照输出读会以为标题写错了） |
| **CE-5** | **评审包 `:74-76`** | `-- backend/app/seed:`<br>`(none)-- backend/data/national_standard_2014.csv:`<br>`(none)\`\`\`` | 三段之间**缺换行**，`(none)` 与下一个小标题、以及收尾的 ``` ``` ``` 全部粘在一行。是生成脚本拼接时漏了 `\n` | 成立（Minor，排版；但它是**评审者要据以判断禁区的那一段**，粘连会让「(none)」的归属看不清） |
| **CE-6** | **账本 P2-D4（`progress.md:1075`）** | 「亲验 **`test_layering.py:172`** 的空转守卫下界是 8、实测 24 → 加 2 个文件变 26」 | 在**预检基线 `e09e5f6`** 上，`assert len(scanned) >= 8` 在 **`:436`**（HEAD 上 `:466`）；`e09e5f6` 的 `:172` 是 `for alias in node.names:`（`_imported_modules` 的循环体）。**内容全对**（下界确是 8；`e09e5f6` 上 `pipeline 7 + db 11 + domain 6 = 24` ✓；Task 2 主体 +2 = 26 ✓；fr1 再 +1 = 27 ✓，我实跑守卫自己的 `_py_files` 得 7/11/9=27），**只有行号错** | 成立（Minor，行号未绑 rev） |
| **CE-7** | **账本 P2-A4（`progress.md:999`）** | 「`ITEM_BUCKET[ScoredItem.BMI] is None`（BMI 天然不属于任何短板桶，**Plan 01 Ruling 19 的口径**）」 | Plan 01 账本 `:170` 的 **Ruling 19 = 「`raw_from_score` 对非单调序列抛 `ValueError`，不得返回哨兵」**，讲的是反查函数的护栏；「BMI 不参与短板判定与桶化」在 **`:133`（Ruling 17 的关切 1）**。⚠️ **这条错误已从账本传播进 2 份源码**（→ 源码 finding **I-5**） | 成立（Important：它是 I-5 的源头，且违反硬规矩 #55「引用编号前先 grep」——#55 是 Task 1 fix round 4 立的） |

### 4.2 歧义（1 条）

| # | 位置 | 原文 | 判读 |
|---|---|---|---|
| **CE-8** | **派单 §3-C** | 「**P2-A6 的裁定是否真落地**：…`app/db/models/prescription.py:11` 那处**按名字引用**是否同步更新」 | **歧义**。`:11` 是 **`fb5bddb`** 上的位置（实测 `git show fb5bddb:backend/app/db/models/prescription.py` 第 11 行 = `` ``tests/db/test_models.py::test_all_fourteen_tables_created`` 用 ``==`` 钉住了表集合`` ✓ 与 P2-A6 的描述逐字相符）；在 HEAD 上那处引用已随 docstring 重写落到 **`:17`**，且**已同步更新为 `test_all_fifteen_tables_created`** ✓。派单**没说这个 `:11` 绑哪个 rev**，读者会先去 HEAD 上找 `:11`（那里是「`prescription_template` Task 3」那一行）而以为引用没改。**实质：裁定已落地，派单的行号是历史值且未标注。** |

### 4.3 不成立（我核过、控制者是对的）

| 我核的对象 | 亲验结果 | 判定 |
|---|---|---|
| 派单 §0「评审包 **210 927 B / 3229 行**，覆盖 `fb5bddb..966eae0`」 | `read_bytes()` → **210927 B**；LF 计数 **3229**（文件末有换行，`split` 后 3230 项）；区间内 5 笔 commit 逐字相符 | ✅ **不成立**（派单对） |
| 派单 §0「`progress.md`（约 **215 KB**）」「`task-2-report.md`（约 **128 KB**）」「`task-2-brief.md`（**28 004 B**）」 | **214 986 B** / **127 827 B** / **28 004 B**（第三个逐字节相符） | ✅ 不成立 |
| 派单 §0「HEAD = `7296793`，五笔只动 `.gitattributes`、`.gitignore` 与 `.superpowers/`，**不动 `backend/`**」 | `git diff --name-only 966eae0..HEAD -- backend` → **空** | ✅ 不成立 |
| 派单 §1「`3ea27cc` … **481 → 528 passed**」 | 我跑不了 pytest，但**用测试计数独立复核了这 47 的增量**：`3ea27cc` 上 `test_refdata_prescription.py` 收集 **43** 例（27 个函数，其中 2 个 parametrize ×9/×11；fr2 才加的 2 条不在内）+ `test_prescription_templates.py` **3** 条 = **46**（与实现者报告 §2.5「46 条新测试」逐字相符），再加 `test_generate.py` 新增的 `test_table_partition_is_exhaustive` = **47** = 528 − 481 ✓ | ✅ 不成立（算术自洽） |
| 派单 §1「`c21767d` … domain **406/114 → 441/120**」 | 我实跑 `--cov=app/domain/prescription --cov-branch` 得 `exercises.py **38**/6`、`templates.py **2**/0`、`__init__.py **2**/0`；账本记 fr1 前 `templates.py` 是 5 → `406 + 38 + 2 − 5 = 441` ✓、`114 + 6 = 120` ✓ | ✅ 不成立（增量算术逐格对得上） |
| 派单 §1「`966eae0` … **528 → 531 passed**」 | fr2 新增恰好 3 个测试函数（`test_impact_rank_values_are_pinned_verbatim` / `test_prescription_public_namespace_is_pinned_verbatim` / `test_templates_module_still_reexports_impact_level`，均非 parametrize），且 `git diff --name-status c21767d 966eae0` = **4 个 M、全在 `backend/tests/`** | ✅ 不成立 |
| 派单 §2「裁定编号从 47 跳到 49，**`Ruling 48` 号未使用**（已知勘误）」 | Plan 02 账本 `**Ruling N` 标题序列 = 114 个、1..118、**缺口 = [48, 58, 77, 78]**；`:616` 有 Ruling 58 的编号勘误明写「**编号 48 永久留空，不得回填**」、`:649` 有 Ruling 59 专记此事 | ✅ 不成立（勘误本身是准确的） |
| 派单 §2「硬规矩 **#48–#71 在 Plan 02 账本**；**#1–#47 在 Plan 01 账本**」 | Plan 02 账本：#60–#71 每条都有「补硬规矩 #N：」或「硬规矩 #N 修订」定义行（逐条打印过）；Plan 01 账本：硬规矩编号 min=1 / max=**47** / 42 个不同号，#18/#19/#29/#30/#32/#35/#39/#42 全部命中（#32 有独立标题行「## 硬规矩 #32：`ast.dump` 等价性 + 两组对照」） | ✅ 不成立（**分两处的说法准确**） |
| 派单 §2「Plan 01 账本约 **806 KB**」 | **805 520 B / 4856 LF** | ✅ 不成立 |
| 派单 §3-B「spec §7.2:487 点名 … + 计划 `:182` 要求的速度柔韧类 4 个」 | `:487` 的引文我逐字核过 ✓；「速度柔韧类 4 个」在 **`e09e5f6`（预检基线）的计划 `:182`** 上逐字相符 ✓（在 `fb5bddb` 上是 `:185`、在 HEAD 上是 `:186`） | ✅ 不成立（**绑定 `e09e5f6` 时准确**；建议派单往后的计划行号都标 rev，因为该文件在 Task 2 期间被改过 3 次） |
| 派单 §3-C「`exercise_ref` / `impact_level` / `targets` / `volume_reduction` / `IMPACT_RANK` 各自的所有者是否唯一」 | 逐个核过，**全部唯一**（详见 §1.3 第 3 行）；`impact_level` 的「db 侧类常量 + domain 侧枚举」是本包既有的**约定 2「两处设防」**，且有一条漂移测试，不是新造的第二所有者 | ✅ 不成立 |
| 派单 §3-D「控制者已亲跑过：删 `steady_run` → **1 failed**；删 `bodyweight_resistance` → **4 failed**（指纹 + 三条跨文件守卫）」 | 跑不了 pytest，但**静态可证其必然**：`steady_run` 实测不在任何映射里 → 只有指纹红；`bodyweight_resistance` 是 `plyometric_jump` 两条映射的 `to` → 删掉它会让 `test_equivalence_table_only_maps_to_existing_exercises`、`test_equivalence_never_maps_to_a_higher_impact_level`（`library[mapping.to_ref]` 抛 `KeyError`）、`test_every_high_impact_exercise_has_a_low_substitute`（同一处 `KeyError`）+ 指纹 = **4** ✓ | ✅ 不成立（1 与 4 两个数都自洽） |

### 4.4 我对前两轮实现者所报控制者错误的复核（抽样，不逐条）

账本 Ruling 89–115 已逐条裁定，我抽验了其中**可独立复核**的 8 条，**全部与账本的裁定一致**：

| 账本条目 | 我的独立复核 |
|---|---|
| **Ruling 89 / CE-1**（漏了 `len(json_text_columns) == 8`） | HEAD 上 `test_models.py:187` = `assert len(json_text_columns) == 9` ✓；**静态数出 `mapped_column(JsonText)` 全仓恰好 9 处**（`assessment.py` 2 + `derived.py` 4 + `ops.py` 2 + `prescription.py` 1）✓；`models/__init__.py:20` 的散文已改成「九个列」✓ |
| **Ruling 90 / CE-2**（6 处「对现在的断言」变假） | 逐处核到 HEAD：`session.py:4/:46/:91` 三处都是「15 张表」✓；`models/__init__.py:1` = 「15 张表…**§4.1–§4.4**、§4.6」✓（§4.4 已补）；`:39` = 「**1 张**：Task 2 的 `exercise`；Task 3/9 再加 3 张」✓；`:77-80` 已重写成「`feedback` 今天仍为空…`prescription` 的导入自 Plan 02 Task 2 起是**承重的**…」✓；`_shared.py:3-7` = 「**五个**表模块（`organisation`/`assessment`/`derived`/`ops`，以及 Plan 02 Task 2 起也用了它们的 `prescription`）」✓ |
| **Ruling 101 / CE-1**（`refdata.py:21` 应为 `:29`） | HEAD `refdata.py:29` = `from app.domain.tables import StandardTable` ✓；`:21` = 「让 `app/refdata.py` 承担一份处方侧的知识。」（docstring 里的一句中文）✓ **账本的勘误逐字准确** |
| **Ruling 104 / CE-8**（`level == 2` 在真仓不存在） | 全仓相对导入实测 **level 分布 = `{1: 15}`**，`level == 2` **0 条** ✓；`app/domain/prescription/` 那 2 条都是 `level=1 module=exercises` ✓ |
| **Ruling 106 / CE-6**（「12 条」的份数与绑 rev） | `git grep "12 条"` → **purity 1 处（`:459`）+ layering 2 处（`:160`/`:265`）**，与账本 `:1307` 记的「purity 残留 1、layering 残留 2」**逐字相符** ✓；三处全部绑了 rev ✓ |
| **Ruling 106 / CE-7**（`:74` 的 3 处过期数字） | `git grep "__init__.py:74"` → **0**；`git grep "__init__.py 74 1 None"` → **0** ✓ 与账本 `:1310` 相符；剩下的 3 处 `:74` 都是**解释这次推移**的散文 ✓ |
| **Ruling 113 / CE-12**（把「14 条」归因为「数错」是错的） | 我在 **4 个 rev** 上用 `git ls-tree` + `git show`（**没有 checkout**）重算：`6a2938f` **12** / `7b84599` **12** / `3ea27cc` **14** / `c21767d` **15**，且 `3ea27cc` 的那 14 = `app/db/models` **13** + `app/domain/prescription/__init__.py:10 from .templates import ImpactLevel` **1** —— **与账本 Ruling 113 的更正逐格相符**，即前任实现者的「14」在它测量的 rev 上是对的 ✓ |
| **Ruling 116**（数据丢失事故的取证物） | `.superpowers/_snapshots/20261007-174217/` 实测 **96 个文件 / 4 416 480 B** ✓ **逐字相符**；`task-1-report.TRUNCATED-20261007-174217.md` 实测 **77 837 B / 1031 LF** ✓ **逐字相符**；`task-1-report.md` 现 **245 229 B / sha256[:16] `292F6251FD45AE8E`** ✓、`task-2-report.md` **127 827 B / `6F1851079C3F6031` / CRLF 946 + 裸 LF 23** ✓、`progress.md`@`7c5aff8` **211 499 B / `A327D60E37C92021` / CRLF 1415** ✓ —— 账本 `:1412-1414` 那张终验表**三行全部逐字复现** |

---

## 5. 正面确认（抽验控制者/实现者给出的路径、行号、数量、基线、指纹 —— 无论对错都报）

### 5.1 三个指纹 + 禁区（全部逐字相符）

> **哈希口径**（两种，别混）：`backend/data/*`（`.gitattributes` 钉 `text eol=lf`，工作树本来就是纯 LF）用**CRLF 归一化后**的 sha256[:16]，与测试里 `_fingerprint()` 的口径一致；`backend/**/*.py`（工作树是纯 CRLF）用**裸字节**的 sha256[:16]，与账本 Ruling 108 记的`exercises.py = 1FC9AA42A6B93BF5` 同口径。下表逐个标注。

| 对象 | 账本/派单印的值 | 我的实测（`read_bytes()` + CRLF 归一化） | 判定 |
|---|---|---|---|
| `backend/data/exercises.yaml` | 13358 B / `A6A000F58815FCBB` / CRLF 0 | **13358 B / `A6A000F58815FCBB` / CRLF 0** | ✅ |
| `backend/data/exercise_equivalence.yaml` | 7841 B / `0FFB881574AC04F3` / CRLF 0 | **7841 B / `0FFB881574AC04F3` / CRLF 0** | ✅ |
| `backend/data/national_standard_2014.csv` | 21412 B / `D2C8E539E2FA0029` / CRLF 0 | **21412 B / `D2C8E539E2FA0029` / CRLF 0** | ✅ |
| 测试里钉的两个常量 | — | `test_refdata_prescription.py:69` = `"A6A000F58815FCBB"`、`:72` = `"0FFB881574AC04F3"`，**与磁盘现值逐字相符** | ✅ |
| `backend/app/domain/prescription/exercises.py`（**裸字节**口径） | `1FC9AA42A6B93BF5`（账本 `:1281`） | **12384 B / CRLF 200 / `1FC9AA42A6B93BF5`** | ✅ |
| `backend/pe.db` | 不得存在 | **不存在** | ✅ |
| `backend/data/seed/` | 0 文件 | **存在、`os.listdir()` = `[]`** | ✅ |

### 5.2 账本/报告里的行号与数量（抽验 20 项，**全部相符**）

| 陈述 | 出处 | 我的实测 |
|---|---|---|
| `app/refdata.py:29` = `from app.domain.tables import StandardTable` | Ruling 96/101、`refdata_prescription.py:34`、`exercises.py:5` | ✅ 逐字相符（HEAD） |
| `app/refdata.py:21` 是 docstring 里的一句中文 | Ruling 101 | ✅ =「让 `app/refdata.py` 承担一份处方侧的知识。」 |
| `app/db/models/__init__.py:82` = `from . import feedback, prescription` | Ruling 106/CE-7、两份守卫的新散文 | ✅ 逐字相符；`git grep -n "import feedback" -- backend/app` → **恰好 1 处** ✓（守卫里印的取证命令我跑了，命中数相符） |
| `models/__init__.py:74` 今天是 `from .derived import *  # noqa: F401,F403` | purity 守卫 `:107` | ✅ 逐字相符 |
| 那条命令在 `c21767d` 上打出来的**第 7 行**是 `app/db/models/__init__.py 82 1 None`，且**序数 7 在四个 rev 上都没变** | layering 守卫 `:172-176` | ✅ **完全复现**：我按四个 rev 逐个重算，`6a2938f`/`7b84599` 的第 7 行是 `… __init__.py **74** 1 None`、`3ea27cc`/`c21767d`/`966eae0` 是 `… __init__.py **82** 1 None`——**序数恒为 7、变的只是行号**，与它写的一字不差；`__init__.py` 恒有 **7** 条相对导入、`module=None` 那条恒排最后 ✓ |
| 全仓相对导入 **12 / 12 / 14 / 15**（`6a2938f`/`7b84599`/`3ea27cc`/`c21767d`） | Ruling 106/113、两份守卫 | ✅ 逐 rev 相符；`c21767d`/HEAD = `app/db/models` **13** + `app/domain/prescription` **2**、level 分布 `{1: 15}`、`module=None` **1** 条 ✓ |
| `_absolute('exercises', 1, ('app','domain','prescription'))` = `'app.domain.prescription.exercises'` | purity 守卫 `:464-466` | ✅ 实跑两份守卫的 `_absolute`，**都返回这个串** |
| `_is_forbidden('app.db.models._shared') is False`、`_is_forbidden(<domain 那 2 条>) is False`、`_is_allowed(<domain 那 2 条>) is True` | layering `:266-270` | ✅ 实跑全部相符 |
| `_package_of(BACKEND/'app/domain/prescription/match.py')` = `('app','domain','prescription')`；`_absolute('indicators',2,…,'X')` = `'app.domain.indicators'`；与 `resolve_name('..indicators','app.domain.prescription')` 相符 | layering `:277-280`、账本 P2-B1 `:1042` | ✅ 三份实测全部逐字相符（`resolve_name` 也返回 `app.domain.indicators`） |
| **`app.db.seed` 在两份守卫下判定相反** | 派单 §4（硬规矩 #56） | ✅ **复现**：`layering._is_forbidden('app.db.seed') = False`（GREEN）/ `purity._is_allowed('app.db.seed') = False`（RED）——**同一个折算串两边颜色相反**，正是派单警告的那个陷阱 |
| allow-list = **6** 个标准库模块串 + `app.domain` 前缀，且**未被放宽** | `refdata_prescription.py:28-30`、`templates.py:32-33`、账本 Ruling 101 | ✅ `ALLOWED_MODULES` 实测 `frozenset({'dataclasses','enum','collections','collections.abc','numpy','typing'})` = 6 个，在 4 个 rev 上逐字相同；`ALLOWED_PACKAGE='app.domain'` |
| `exercises.py` 的 import 只有 4 条，且「三个标准库串命中 `ALLOWED_MODULES`、第四个命中前缀 `app.domain.`」 | `exercises.py:17-19` | ✅ AST 实测 4 条（`collections.abc`/`dataclasses`/`enum`/`app.domain.indicators`）；实跑 `_is_allowed` 四个都 True，前三个确实在 `ALLOWED_MODULES` 里、第四个靠 `app.domain` 前缀 |
| 「既有 **4** 个 domain 模块全部用绝对串」 | Ruling 104、layering 守卫 `:270` | ✅ AST 扫 `app/domain`：`derive.py` / `indicators.py` / `percentile.py` / `stratify.py` **恰好 4 个**用 `app.*` 绝对串（`tables.py` 与两个 `__init__.py` 不用）；`exercises.py:41` 同风格 |
| `dir(pkg)` 的公有名 = `['EQUIVALENCE_TRIGGERS','EquivalenceMapping','EquivalenceTable','ExerciseSpec','IMPACT_RANK','ImpactLevel','TARGET_DOMAIN','exercises']`，且**随导入顺序漂** | `test_refdata_prescription.py:811-816` | ✅ **全新解释器**下逐字相符（8 个）；在我这个已 import 过 `templates` 的进程里变成 **9** 个（多出 `templates`）——**它说的「漂」被我不小心亲自演示了一遍** |
| `dir(exercises)` 的公有名共 **11** 个，其中 4 个是模块级 import 进来的（`Mapping`/`dataclass`/`Enum`/`ITEM_BUCKET`）、一个都没被重导出 | `test_refdata_prescription.py:822-825` | ✅ 实测 **11** 个，那 4 个逐个在内；`__all__` 是 7 个、7 + 4 = 11 ✓ |
| `_MODELS_PUBLIC_BASELINE` = **33** 个名字，且「里面含一批偶然公有的名字（`dt` / `json` / `Boolean` / `mapped_column` …）」 | `test_refdata_prescription.py:819-821`、`:841`、`:885` | ✅ AST 取出字面量 **33** 个；`dt`/`json`/`Boolean`/`mapped_column` **四个逐个在内**；`test_models.py:469` 的 `len(...) == 33` 自校也在 ✓ |
| `_MODELS_SUBMODULES` 排除**六个**子模块名 | `test_refdata_prescription.py:815` | ✅ `frozenset({'organisation','assessment','derived','prescription','feedback','ops'})` = 6 ✓ |
| Plan01 **Ruling 144**：`derived_metrics.trend String(16)`、`"insufficient_data"` 是 17 字符、**隔了 7 个任务** | `test_refdata_prescription.py:542-544`、`test_models.py:348-350` | ✅ Plan01 账本 `:1585-1588` 逐字对上（「列宽 16」「17 字符」「隔了 **7 个任务**、5 轮评审」「列宽改 **20**」）；HEAD 上 `derived.py:152` = `String(20)` ✓ |
| Plan01 **Ruling 213 / 231 / 28 / 1** 被引的主题 | `test_refdata_prescription.py:5-6`/`:65-67`、`prescription.py:18`、`_shared.py:9-10` | ✅ 四条逐个核过：213 = 「CSV 是唯一不可由代码重推的知识资产、实质无守卫」、231 = 「裸字节哈希随 `core.autocrlf` 漂」、28 = 「`>=` 改 `==` 防提前建表」、1 = 「`sorted(n for n in dir(models) if not n.startswith('_'))` 字面基线」——**引用主题全部正确** |
| `.gitattributes:14` = `backend/data/*.yaml  text eol=lf` | P2-A7、`test_refdata_prescription.py:67-68` | ✅ 逐字相符（`:13-15` 三条 = `*.csv`/`*.yaml`/`*.md`） |
| `TOTAL 441 stmts / Miss 2 / **99%**`（MB4 相位 2 的预测） | `test_prescription_templates.py:117-118` | ✅ **算术与格式双双成立**：`coverage.results.Numbers(n_statements=441, n_missing=2, n_branches=120, n_partial_branches=0, n_missing_branches=0)` → `pc_covered = 99.6434…`、`pc_covered_str = **'99'**`（coverage 刻意不把 99.5+ 显示成 100；同一 API 在 Miss 0 时给 `100.0`/`'100'`）。我自己的 scoped 运行 `TOTAL 42 9 6 0 → 69%` 也与 `Numbers` 的 `68.75 → '69'` 相符 |

### 5.3 我实跑复现的两条最关键取证

**① MB4 相位 2（Ruling 103 / 硬规矩 #67 的「退出码 0 的静默退化」）—— 完全复现 ✅**

方法：把 `tests/domain/test_prescription_templates.py` **复制到 `$env:TEMP`**，按 MB4 相位 2 的定义改两处 import
（`from app.domain.prescription import exercises, templates` + `from …templates import ImpactLevel`
→ 两句都指 `exercises`），并去掉 fr2 那条新守卫（等价于 deselect）。**仓库里的文件一个字节没动**
（跑前跑后 sha256[:16] 都是 `B71E435CF3FC577C`，脚本自己断言了这一点）。串行跑，不与任何别的命令并行（硬规矩 #62）。

```
### BASELINE (unmodified guard file, known GREEN)
$ cd backend; python -m pytest tests/domain/test_prescription_templates.py -q -p no:cacheprovider
        -c pyproject.toml --cov=app/domain/prescription --cov-branch --cov-report=term-missing
Name                                   Stmts   Miss Branch BrPart  Cover   Missing
app\domain\prescription\__init__.py        2      0      0      0   100%
app\domain\prescription\exercises.py      38      7      6      0    70%   194-200
app\domain\prescription\templates.py       2      0      0      0   100%
TOTAL                                     42      7      6      0    73%
4 passed in 0.12s
>>> EXIT CODE = 0

### M-B4 PHASE 2 (both imports redirected to `exercises`, guard test removed)
$ cd backend; python -m pytest $env:TEMP\rv2_mb4_qxzmow4z\test_mb4_phase2.py -q … --cov=app/domain/prescription --cov-branch …
app\domain\prescription\__init__.py        2      0      0      0   100%
app\domain\prescription\exercises.py      38      7      6      0    70%   194-200
app\domain\prescription\templates.py       2      2      0      0     0%   37-39     ← 归 0
TOTAL                                     42      9      6      0    69%
4 passed in 0.98s
>>> EXIT CODE = 0                                                                  ← 退出码仍是 0
```

**判读**：`test_prescription_templates.py:112-122` 印的每一格都被复现——
`templates.py` 从 `2 0 0 0 100%` 变成 **`2 2 0 0 0%`**、Missing 列 **`37-39`**（**连 `37-39` 这个写法都一字不差**：
第 38 行是空行、不是语句，coverage 仍把它并进区间）、而 **`pytest` 退出码 = 0、`4 passed`**。
这就是账本 Ruling 103 说的「**退出码 0 但不变量已破**」，也是硬规矩 #67 的实证基础。
**它成立**，因此 fr2 加的那条守卫（让自己也成为 `templates` 的导入方）**是承重的**：
`git grep -n "^from app.domain.prescription.templates import" -- backend` 实测**恰好 1 处** =
`tests/domain/test_prescription_templates.py:45`，即那条守卫连同顶部那句 `from app.domain.prescription import exercises, templates`
是 `templates.py` 今天**唯一**的两个导入方 ✓（守卫散文 `:102-105` 印的两个命中数 **1** 与 **2** 我都跑了，逐字相符）。
**唯一没被复现的是绝对数**（`TOTAL 441 / Miss 2 / 99%`、`529 passed, 1 skipped`）——那要全量套件，见 §6-2；
但 §5.2 已用 `coverage.results.Numbers` 独立证明了 `441/2/120/0 → '99'` 的算术与格式都对。

**② M-C3（Ruling 112：往 `exercises.py` 加一个公有定义、不重导出 → 只有 AST 穷尽支变红）—— 复现 ✅**

方法：把 `exercises.py` 复制到 `$env:TEMP`，在 `EQUIVALENCE_TRIGGERS` 之前插入
`SUBSTITUTE_POLICY = "first_match"`（与实现者用的同一个名字），**先确认锚点命中、字节真的变了**
（原 `1FC9AA42A6B93BF5` → 变异副本 `847772DFAC16F71B`），再对副本跑支 5 的那段 AST 抽取逻辑
（逐字抄自 `test_refdata_prescription.py:904-913`）。**仓库文件跑后仍是 `1FC9AA42A6B93BF5`** ✓（脚本自己断言）。

```
baseline defined == set(_PRESCRIPTION_PUBLIC_BASELINE) -> True        ← 已知 GREEN 的对照（硬规矩 #53）
mutated  defined = ['EQUIVALENCE_TRIGGERS','EquivalenceMapping','EquivalenceTable','ExerciseSpec',
                    'IMPACT_RANK','ImpactLevel','SUBSTITUTE_POLICY','TARGET_DOMAIN']
mutated  defined == baseline -> False   extra = ['SUBSTITUTE_POLICY']
```

**判读**：`__all__` 一个字没改，故支 1（`len(baseline)==7`）、支 2（`list(pkg.__all__)==baseline`）、
支 3（基线不是字母序）、支 4（`getattr` 同一性）、支 6（合成反面对照）**全部不受影响**；
**只有支 5 的 `defined == baseline` 变假** —— 与实现者报的「**只有支 5 红**、`1 failed, 530 passed`」一致 ✓，
也证实了账本 Ruling 112 的结论：**那种场景下纯字面断言结构性地不可能开火，AST 穷尽支是唯一的守卫**。
实现者刻意不用 `dir()` 的理由我也复核了（`dir(pkg)` 实测会多出子模块属性、且随导入顺序漂 → §5.2）。

### 5.4 其余逐支真值（模拟复现，非 pytest）

`test_impact_rank_values_are_pinned_verbatim` 的四支，我用改过的秩字典逐支重算（`review2_probes/p13_mut.py` E4.1）：

| 相位 | 支 1（字面字典） | 支 2（按秩排序 == `IMPACT_DESCENDING`） | 支 3（`LOW >= HIGH`） | 支 4（`not HIGH >= LOW`） | 与 docstring `:493-499` 的声称 |
|---|---|---|---|---|---|
| **REAL**（已知 GREEN 对照） | True | True | True | True | 「绿输入 = 今天的真值（支 1、2、3 都实跑通过）」✅（支 4 也 True） |
| **M-A1**（`HIGH:0 ↔ LOW:2`） | **False** | **False**（排出来是 `['low','medium','high']`） | **False** | **False** | 「**四支全部不成立**」✅ **逐支相符** |
| **M-A2**（三值全 `0`） | **False** | True（`sorted` 稳定，键全等 → 保持插入序 `high,medium,low`） | True（`0>=0`） | **False** | 「**支 2 与支 3 仍是绿的，只有支 1 与支 4 不成立**」✅ **逐支相符** |

并且两个相位都会让 `test_lookup_honours_...` 红（M-A1 打真表那三行、M-A2 只打合成表那行 `synthetic.lookup("a", LOW) is None`）
→ 两者的「`2 failed, 529 passed`」都自洽 ✅（`529 + 2 = 531`）。

「不升冲击」相位的**断言分支归属**（硬规矩 #65 第 ① 项要求指明哪一支开火）：
`test_equivalence_never_maps_to_a_higher_impact_level` 有两支——**序支** `rank[target] < rank[source]`（`:323`）
与**声明一致支** `mapping.max_impact.value != target`（`:329`）。实算真表：
`from` 全为 `high`、`to` 全为 `low` → **序支在真实数据上结构性不可达**（0 offender），
故「把某个 high 的等价物改成另一个 high」只会开**声明一致支**——与实现者报告 §6.1 错误 6 的取证文本一致 ✅，
也与账本 Ruling 95（控制者错误 #104）的裁定一致 ✅。实现者自加的 ①′（把 from/to 写反造 `low → high`）
是证明序支不是死代码的正确做法 ✅（我未能实跑，但序支的判据 `rank[target] < rank[source]` 在 `low→high` 上
`0 < 2` 为真、必然开火，静态可证）。

### 5.5 评审包本身的保真度

| 项 | 实测 |
|---|---|
| 嵌入的 `exercises.yaml` 全文（评审包 `:1183-1449`） | 与磁盘那份**逐字节相同**（解码后 9308 字符 == 9308 字符） |
| 嵌入的 `exercise_equivalence.yaml` 全文（`:1456-1581`） | **逐字节相同**（5154 == 5154） |
| `git log --oneline` / `git diff --stat` / `git diff --name-status` 三段 | 我重跑同一条命令，输出**逐字被包含在评审包里** ✅ |
| `diff --stat` 的合计 | `19 files changed, 2472 insertions(+), 62 deletions(-)` ✅ 与我自己跑的相符 |
| ⚠️ 「禁区命中」那一段 | 标题与内容自相矛盾 + 缺换行 → **CE-4 / CE-5** |

---

## 6. 不可复核项（12 条）

| # | 陈述 | 为什么不可复核 |
|---|---|---|
| 1 | **`531 passed`（HEAD）/ `528 passed`（`3ea27cc`、`c21767d`）/ `481 passed`（基线）** | 全量 `pytest` 收集期即失败（§0）。**已用测试计数独立交叉核对**：46 + 1 = 47 = 528 − 481 ✓、fr2 +3 = 531 ✓ |
| 2 | **domain 分支覆盖 `441 stmts / Miss 0 / 120 branch / BrPart 0 / 100%`、`530 passed, 1 skipped`**（Global Constraint #2 的验收命令） | 需要全量套件（domain 的行被 `tests/db`、`tests/pipeline`、`tests/integration` 等大量非 domain 测试执行到）。**部分实测**：`--cov=app/domain/prescription --cov-branch` 下 `exercises.py 38/6`、`templates.py 2/0`、`__init__.py 2/0` 与账本逐格相符；`406+38+2−5=441`、`114+6=120` 自洽。**但「Miss 0 / BrPart 0 / 100%」这三个数我没能独立验证** —— 这是本轮最大的取证缺口，**建议解除 §0 的阻塞后由控制者补跑一次** |
| 3 | 实现者报的 **12 个变异相位**（M-A/M-B/M0/M1a/M1b/MA1/MA2/MB1–MB4/MC1–MC3）作为 **pytest 运行** | 同上。**我实跑/复现了其中 4 组**：MB4 相位 2（真 coverage + 真 pytest，§5.3-①）、MC3（AST 支 5，§5.3-②）、MA1/MA2（四支逐支，§5.4）、以及「不升冲击」的分支归属（§5.4）。**未复现**：M-A（`>=`→`>`）、M-B、M0、M1a/M1b（语义等价改写）、MB1/MB2/MB3、MC1/MC2 |
| 4 | `test_exercise_ref_is_unique_at_the_db_level` / `test_exercise_impact_level_check_rejects_unknown_value` 真的抛 `IntegrityError` | 需要 sqlalchemy 建 DDL。**静态复核**：`prescription.py:116` 有 `unique=True`、`:129-131` 有 `_in_domain("impact_level", IMPACT_LEVELS, "ck_exercise_impact_level")`；`_shared.py:28-29` 生成的文本我静态算出是 `impact_level IN ('high', 'low', 'medium')` ✓。**但「SQLite 真的拒绝 `very_high`」未实跑** |
| 5 | `sync_exercises` 的幂等 / 就地更新 / 返回行数（`test:610-669`） | 需要内存库 session。**静态复核**：`refdata_prescription.py:388-406` 走 `repo.upsert(session, Exercise, ("ref",), {...})` + `session.flush()` + `return len(library)`；`repo.py:26` 明写「更新分支是 PATCH 语义」✓ |
| 6 | `test_exercise_string_column_widths_fit_the_yaml_values` 从 ORM 读 `.type.length` 的实际结果 | 需要 sqlalchemy。**已用 AST 静态复核**：`String(48)/(64)/(256)/(8)/(32)` 对 YAML 实测最长值 `29/12/62/6/13` **全部容得下** ✓ |
| 7 | `_in_domain_columns()` 在运行时反解出 **11** 列 | 需要 `Base.metadata`。**静态枚举**：`test_models.py:356-360` 列的 11 个我逐个在源码里找到了对应的 `_in_domain(...)` 调用位置，且 `exercise.impact_level` 在内 ✓；`mapped_column(JsonText)` 也静态数出 **9** 处 ✓ |
| 8 | 历史墙钟与运行时长（`528 passed in 82.73s`、`531 passed in 55.89s`、`481 passed in 54.91s`、`406/114` 那次跑的时间） | 依赖当时的机器状态；且本机现在连收集都过不去。**账本自己也按硬规矩 #19 标了「历史实测」** |
| 9 | 「实现者/控制者**没有跑过** `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`」（D3 禁区纪律） | 无法回溯他人的命令历史。**只能验后果**：`backend/pe.db` 不存在 ✓、`backend/data/seed/` 0 文件 ✓ → 后果性证据干净 |
| 10 | 「终审 M4（改评分表一处 `raw_value`、全仓只有指纹红）」（`test_refdata_prescription.py:170-171`） | Plan 01 终审的历史运行。**已核它引的 Ruling 213 主题正确** ✓（Plan01 账本 `:4034`） |
| 11 | Ruling 116 的**时间线**（两份报告在 `16:44:35` 同一秒被截断、`Read` 当时报 1031 / 617 行、全 `$env:TEMP` 扫过 91 个候选文件） | 依赖当时的 IDE 状态与 TEMP 内容。**取证物我已核**：`_snapshots/20261007-174217/` = **96 文件 / 4 416 480 B** ✓、`task-1-report.TRUNCATED-…md` = **77 837 B / 1031 LF** ✓、三份文件的 sha16 与账本 `:1412-1414` 逐字相符 ✓ |
| 12 | `exercises.yaml:91`/`:155` 的运动生理学数值（跑的冲击峰值 **2–3 倍体重**、快走降到 **约 1.2 倍**） | 仓内无出处、无测量口径；不是本仓可以实跑的东西。→ 已作为 **M-6** 报出（要求补出处或标「无出处、不被守卫」） |

---

## 7. 落盘闸门与收工自证

### 7.1 本文件的双向串查（硬规矩 #48 升级口径）

| 检查 | 结果 |
|---|---|
| 新串命中数 ≥ 1 | 抽 **14** 个只可能出现在本文件的串（结论、阻塞证据、变异输出行、指纹、取证物尺寸…），
  **14/14 命中 ≥ 1**（脚本 `review2_probes/p29_verify.py` 的 `NEW` 列表） |
| 旧串/占位符残留数 = 0 | 查 **7** 类常见占位标记，**首跑命中 4 类、各 1 次，且 4 次全部落在本节这一行自己身上**
  （即「描述这道检查的那句话里写出了被检查的 token」——与实现者 fr2.9-2 记的「grep 计数会被自己的散文改变」
  是同一形态）。已把 token 从正文里挪走、只留在脚本的 `OLD` 列表里；**改后复跑 = 7 类全部 0 命中** ✅ |
| 字节数 / 行数 / 行尾 / sha256[:16] | 落盘首版 **89 408 B / 770 LF / CRLF 0（纯 LF）/ `B7A38659ECE7A45A`**；
  ⚠️ **本节刻意不印本文件自己的「终版」字节数 / 行数 / sha256**——那是自指：把终版指纹印进去这个动作本身就会改变它（与 `test_prescription_templates.py:107-109` 拒绝把「会被自己的散文改变的 grep 计数」写进散文是同一条纪律）。两个**已成为历史、因而可复核**的定点是：落盘首版 `89 408 B / 770 LF / CRLF 0 / B7A38659ECE7A45A`、首版修订版 `90 081 B / 774 LF / CRLF 0 / 0A5F3A651DE15CF4`；终版实测值由脚本 `review2_probes/p31_fix2.py` 的 stdout 与评审者的返回消息承担。全部用 `read_bytes()` 量，**未用** `read_text()`（硬规矩：后者做换行翻译、量不到 CRLF） |

### 7.2 收工自证

| 项 | 值 |
|---|---|
| `git rev-parse HEAD` | `7296793c7b439e65d7de8812b361e8d315067d58`（**仍是 `7296793`** ✓） |
| `git rev-parse --abbrev-ref HEAD` | `feature/plan-02-prescription-engine` ✓ |
| `git status --short` | **3 行**（全部是 `.superpowers/` 下的未跟踪新增，**`backend/` 与 `Document/` 零改动**）：<br>`?? .superpowers/sdd/2026-10-06-…/task-2-review-package.md`（**交接时就已经是未跟踪状态**，不是我造的）<br>`?? .superpowers/sdd/2026-10-06-…/task-2-review.md`（本报告）<br>`?? .superpowers/sdd/review2_probes/`（14 个探针 + 7 个输出） |
| ⚠️ 关于派单 §0「收工时 `git status --short` 必须 0 行」 | **按字面不可满足**，且**交接时就不是 0 行**（评审包本身未跟踪，1 行）。评审者是 read-only、不得 commit；而硬规矩 #68 修订版第 (1) 条要求「每轮结束时 `.superpowers/` 的改动必须与代码改动一起 commit」——**那是控制者的动作**。请控制者把这三项一起提交，届时 `git status --short` 归 0 |
| `git diff --name-only 966eae0..HEAD -- backend` | **空** ✓（代码基线 `966eae0` 未被后续五笔触碰） |
| `git diff --name-only fb5bddb..HEAD -- backend/app/seed` | **空** ✓（Global Constraint #10） |
| `git diff --name-only fb5bddb..966eae0 -- .gitattributes .gitignore` | **空** ✓ |
| `backend/pe.db` | **不存在** ✓ |
| `backend/data/seed/` | **存在、0 文件** ✓ |
| `backend/data/exercises.yaml` | **13358 B / CRLF 0 / `A6A000F58815FCBB`** ✓ |
| `backend/data/exercise_equivalence.yaml` | **7841 B / CRLF 0 / `0FFB881574AC04F3`** ✓ |
| `backend/data/national_standard_2014.csv` | **21412 B / CRLF 0 / `D2C8E539E2FA0029`** ✓ |
| `backend/app/domain/prescription/exercises.py` | **12384 B / `1FC9AA42A6B93BF5`** ✓（变异副本跑前跑后一致） |
| `backend/tests/domain/test_prescription_templates.py`（**裸字节**口径） | **10697 B / CRLF 147 / `B71E435CF3FC577C`** ✓（MB4 用的是 `$env:TEMP` 副本，跑前跑后一致） |
| 执行过的破坏性 git 命令 | **0 次**（无 `checkout` / `restore` / `switch` / `merge` / `clean` / `add` / `commit`） |
| 探针位置 | `.superpowers/sdd/review2_probes/`（`p00`/`p01_sizes`/`p02_toc`/`slice`/`src`/`p03_blobs`/`p05_plan`/`p06_planrev`/`p07_env`/`p08_pyd`/`p09_dll`/`p10_structure`/`p11_facts`/`p12_data`/`p13_mut`/`p14_mb4`/`p15_static`/`p16_hist`/`p17_more`/`p18_rulings`/`p19_xref`/`p20_arch`/`p21_arch2`/`p22_arch3`/`p23_residue`/`p24_pkg`/`p25_cov`/`p26_covnum`/`p27_final`/`p28_rules`）+ `$env:TEMP\rv2_ck\`、`$env:TEMP\rv2_mb4_*\`（后者已被脚本自己 `rmtree`） |

---

## 8. 给控制者的处置建议（按优先级）

1. **先解除 §0 的环境阻塞**（关 Smart App Control 或给 `sqlalchemy/sql/_cache_key_cy.cp311-win_amd64.pyd` 加白名单），然后**补跑一次**
   `cd backend; python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing`，
   把 Global Constraint #2 的 `441 / Miss 0 / 120 / BrPart 0 / 100%` 亲自确认一遍——这是本轮**唯一没被独立验证的验收判据**。
   ⚠️ 顺带记一条：**这个阻塞会让 Task 3 起的所有实现者都跑不了测试**，它比本报告里任何一条 finding 都更挡路。
2. **修 7 条 Important**，注意其中 3 条要动被指纹钉住的文件：
   - I-3 / I-6 在 `backend/data/*.yaml` → 改完必须同步 `EQUIVALENCE_FINGERPRINT` / `EXERCISES_FINGERPRINT`；
   - I-7 在 `Document/…spec.md` → Task 2 的授权已用尽，**须另开授权或并入 Task 12 Step 3**；
   - I-1 / I-2 / I-5 各有 2–3 份副本 → **硬规矩 #51：逐份修，并在报告里列出份数**；
   - I-4 建议照 fr2 已确立的口径改成「可 grep 的原文 + 绑 rev」，**不要只是把三个数字换成新的**（那样下一次编辑又会过期）。
3. **勘误账本 P2-A4**（CE-7）——它是 I-5 的源头，不改会让 Task 3/4 第三次抄错。
4. **给派单加一道机械自查**：账本 `:1293` 已经裁定「Task 3 起，派单末尾的自查清单必须由脚本生成」。
   本轮派单仍然手写了 3 个过期/无出处的行数（CE-1/CE-2/CE-3）与 1 个自相矛盾的禁区口径（CE-4）——
   **那条裁定请在派 Task 3 时真的执行**，脚本只需对清单里每个 `路径:行号` 做 `stat` + 打印该行原文、对每个数量做实测。
5. **评审包生成脚本**：把「禁区命中」那一项的路径从 `backend/data` 改成 `backend/data/seed`（并在标题里写清口径），
   同时补上三段之间的换行（CE-4 / CE-5）。
6. Minor 10 条可以并入 Task 3 的预检清单一次性处理；其中 **M-6**（两个生理学数值无出处）建议按
   `volume_reduction` 的同一口径登记（要么给出处、要么显式标「工程估计、不被守卫」）。
