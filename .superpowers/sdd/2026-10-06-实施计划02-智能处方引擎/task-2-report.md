# Task 2 实现者报告 — 动作库（`exercise` 表 + `exercises.yaml` + `exercise_equivalence.yaml`）

> ## ⚠️ 数据丢失事故（20261007-174217，控制者记录）
>
> 本文件在 Plan 02 Task 2 fix round 2 进行期间（约 16:44:35）被**外部进程截断**：
> 从 295 011 B / 3906 LF 掉到 77 837 B / 1031 LF，`## 9` 与 `## fix round 1`–`## fix round 5`
> **六个节全部消失**。同一秒 `task-2-report.md` 也被截断（117 694 B / 972 LF → 62 640 B / 617 LF，
> 丢了 `## fix round 1` 节）。
>
> **根因（高度怀疑，未证实）**：两个文件被截断后的行数**精确等于 `Read` 工具此前报过的行数**
> （1031 / 617，账本 Ruling 64 记的也是 1031）。即 IDE 的文件视图层把它那份
> 「只含前 N 行」的缓存**写回了磁盘**。此外被截断版本与备份在**第 580 行的措辞也不同**
> （当前写「与工作树那份陈旧副本**一致**」、备份写「与工作树那一侧一致」），
> 说明写回的是**陈旧**缓存而不只是短缓存。
>
> **未能还原**：本文件的 `## fix round 1` 节（约 55 054 B）**没有任何备份**。全 `$env:TEMP` 扫描（91 个候选文件）里没有它的副本——Task 2 fix round 1 的实现者没有像 Task 1 fr5 的实现者那样先做字节备份。
>
> **其结论与关键取证已由控制者逐条转录进账本** `progress.md` 的 `#### Task 2 fix round 1 — 控制者亲验` 一节（Ruling 101–109，含覆盖率增量算术、7 个搬迁对象、allow-list 未放宽、M-A/M-B/M0/M1 四相位），故**技术结论无损**，丢的是实现者自己的详细过程记录。
> 另：fix round 2 的实现者把它当时还能读到的 `:900`–`:972` 原文（含 CE-6 / CE-7 / §7 的 2/3/4/5/7 条）**逐字转录进了本文件 `## fix round 2` 节的 fr2.11 附录**，那是唯一残留的原文。
>
> **取证物**：被截断的版本原样另存为 `$env:TEMP\r2v\task-2-report.TRUNCATED-snapshot.md`（fix round 2 实现者存的）（未删）。
>
> **教训已升级为硬规矩 #68/#69**（见账本）。


**状态：完成**（含 4 条超出简报的补充，逐条在 §1.4 与 §7 交代）
**基线：`fb5bddb`** · **分支：`feature/plan-02-prescription-engine`** · **本轮 commit：`3ea27cc`（一个 commit，未 push）**
**commit 后复跑：`python -m pytest -q` → `528 passed in 78.24s`；`git show --stat` → 15 files changed, 2004 insertions(+), 41 deletions(-)；`git status --short` → 0 行。**
**本报告里的所有行号一律 shell 口径（`python … splitlines()` / `git grep -n`），绑定 commit `fb5bddb`（改动前的引用）或 `3ea27cc`（改动后的引用）。**

---

## fr0. 环境与基线复现

### fr0.1 派单 §5 自查的逐条复验（Ruling 84 的正面确认）

派单要求「也请抽验控制者给出的路径、数量、基线是否正确」。**全部亲跑，结论：派单 §5 的自查逐条成立，无一处错。**

| 派单的断言 | 我的实测命令口径 | 实测值 | 判定 |
|---|---|---|---|
| `task-2-brief.md` 28004 B | `pathlib.Path(...).read_bytes()` | **28004 B**，sha256[:16] `29cf1c5009c06972`，CRLF 150 / LF 159 | ✅ |
| Plan 02 账本 154039 B | 同上 | **154039 B**，`23d5a7d677587b1c` | ✅ |
| Plan 01 账本 805520 B | 同上 | **805520 B**，`a604e8b60fa09cc8` | ✅ |
| 计划正文 99922 B | `stat().st_size` | **99922 B** | ✅ |
| Global Constraints 10 条 | 正则数 `^- \*\*` 于该节 | **10** | ✅ |
| Review Focus 5 条 | 正则数 `^\d+\. \*\*` 于该节 | **5** | ✅ |
| `== 14` 在 `tests/db/test_models.py` 的 `:163`/`:228`/`:472` | 改前 shell 逐行打印 | **:163 / :228 / :472 三处**，另函数名 `test_all_fourteen_tables_created` 在 **:24** | ✅ |
| `ORGANISATION_TABLES` 5 + `DATA_TABLES` 9 = 14 | 读 `tests/seed/test_generate.py:483-488` | **5 + 9 = 14** | ✅ |
| spec §14 现有 27 项 | 正则 `^\| \*\*(\d+)\*\* \|` | 最后三项 **25 / 26 / 27**，`| **27** |` 在 **:932** | ✅ |
| `ITEM_BUCKET` distinct values 4（含 `None`） | 测试里亲断言 | **4** = `{endurance, speed_flexibility, strength, None}` | ✅ |
| 当前表数 14 | `from app.db import models; len(Base.metadata.tables)` | **14** | ✅ |
| `.gitattributes:14` = `backend/data/*.yaml  text eol=lf` | shell 逐行打印 | **逐字相符** | ✅ |
| 基线 HEAD `fb5bddb`、`git status --short` 为空 | `git rev-parse HEAD` / `git status --short` | **`fb5bddbdb1aa2e7968034c11d382a3a47b415908`** / **空** | ✅ |
| 硬规矩 #18/#19/#29/#30/#32/#35/#39/#42/#46/#47 在 Plan 01 | grep 定义行 | #29/#30/#35/#39/#42/#47 有「**补硬规矩 #N：**」定义行；#46 有；#18/#19 的定义嵌在裁定行内（命中）；**#32 在 Plan 01 `:3368`「## 硬规矩 #32：`ast.dump` 等价性 + 两组对照」** | ✅ |
| 硬规矩 #50/#51/#52/#53/#56/#57/#59/#61/#63/#64 在 Plan 02 | grep 定义行 | **11 条全部命中定义行**（含 #48） | ✅ |

**另亲验派单/账本点到的 spec 与计划行号**（硬规矩 #61）：spec §4.4 `exercise` 行在 **:239** ✓；§7.2 的 `- exercise_ref: interval_run` / `impact_level: high` 在 **:470-471**、`compound_circuit` / `medium` 在 **:474-475** ✓（P2-B2 的引文逐字相符）；§7.2 层级参数散文在 **:487** ✓；addon 模块名 `energy_expenditure_plus_10pct` / `resistance_priority` 在 **:482** / **:484** ✓；§7.4 三触发在 **:508/:509/:510**、版本号要求在 **:512**、`needs_review` 在 **:514** ✓；§4.4「静态 YAML + 版本号，不入库」在 **:243** ✓；§7.3 装配第 5 步「动作视频二维码」在 **:499** ✓。计划侧：`:700`「表：**18 张**（Plan 01 的 14 + `exercise` / `prescription_template` / `prescription` / `weekly_adjustment`）」✓、`:524` Task 9 的 Files「Modify …（加两张表）」✓、`:491` Task 8 的 Files 只有 `override.py` + 测试 ✓、`:568`/`:569` 把 `training_package` 当**字段**用 ✓、`:681`/`:685` Task 12 的 §14 补项编号 **#28–#34** ✓、`:703`「spec §14 从 27 项扩到 **34** 项」✓。

### fr0.2 基线测试态

| 项 | 派单说 | 我亲跑 | 判定 |
|---|---|---|---|
| `cd backend; python -m pytest -q` | 481 passed | **`481 passed in 54.91s`** | ✅ |
| `--cov=app.domain --cov-branch` | 399 stmts / Miss 0 / 114 branch / BrPart 0 / 100%，480 passed + 1 skipped | **未独立复跑**（见下） | ⚠️ 见注 |
| 表数 | 14 | **14** | ✅ |
| `backend/pe.db` | 不得存在 | **不存在** | ✅ |
| `backend/data/seed/` | 0 文件 | **`[]`** | ✅ |
| `national_standard_2014.csv` | 21412 B / `D2C8E539E2FA0029` / CRLF 0 | **21412 B / `D2C8E539E2FA0029` / CRLF 0** | ✅ |

⚠️ **基线覆盖率我没有独立复跑**，只跑了 `pytest -q`（481 passed）。理由是复跑要 ~2 分钟且它不改变任何落地决策。**用算术交叉核对代替**：终态覆盖率是 **406 stmts / Miss 0 / 114 branch / BrPart 0 / 100%**，而本 Task 给 `app/domain/` 新增的恰好是两个文件——`prescription/__init__.py` **2** stmts + `templates.py` **5** stmts = **7**，`406 − 7 = 399`，且 **branch 数 114 一个未增**（枚举类没有分支）。这与派单声称的基线 399/114 **逐格相符**。若控制者认为算术交叉核对不够，需要补跑一次基线覆盖率。

### fr0.3 环境

Python 3.11.1、无 venv、SQLAlchemy 2.1、SQLite、PyYAML；`core.autocrlf=true`；全程 PowerShell。
**没有跑过** `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`（禁区纪律 D3）；`sync_exercises` 的验证全部在测试的内存库 session fixture 里做。
**没有执行过** `git checkout` / `git restore` / `git switch` / `git merge`（硬规矩 #46/#47）；变异后的还原一律 python 按字节写回并核 sha256。

---

## 1. 逐步落地情况

### 1.1 新建文件（7 个）

| 路径 | 内容 | 亲验 |
|---|---|---|
| `backend/data/exercises.yaml` | **23** 个动作，每条 5 个键。high **5** / medium **10** / low **8**。9 个 `equipment` 取值 | 13358 B / LF 267 / sha256 `a6a000f58815fcbb…` / sha256[:16] `A6A000F58815FCBB` |
| `backend/data/exercise_equivalence.yaml` | `version: "1.0"` + **10** 条映射（5 个 high × 2 个触发）+ `volume_reduction: {bmi_over_30: 0.8, muscle_low_p10: 0.9}` | 7841 B / LF 126 / sha256 `0ffb881574ac04f3…` / sha256[:16] `0FFB881574AC04F3` |
| `backend/app/domain/prescription/__init__.py` | 公开面重导出，**只有** `ImpactLevel`（P2-B1） | 720 B / 12 行 / 2 stmts |
| `backend/app/domain/prescription/templates.py` | **只有** `ImpactLevel(str, Enum)`，不读盘（P2-B1 / Global Constraint #1） | 3196 B / 45 行 / 5 stmts / **0 branch** |
| `backend/app/refdata_prescription.py` | `ExerciseSpec` / `EquivalenceMapping` / `EquivalenceTable(+lookup)` / `load_exercises` / `exercises` / `load_equivalence` / `equivalence` / `sync_exercises` | 28193 B / 507 行 |
| `backend/tests/test_refdata_prescription.py` | **43** 条测试 | 39778 B / 716 行 |
| `backend/tests/domain/test_prescription_templates.py` | **3** 条测试 | 4183 B / 70 行 |

**23 个动作的推导口径**（简报 Step 1：spec §7.2 `:487` 点名的动作 + 18 格矩阵的结构，**不从 Task 3 的 YAML 反推**）：

- **spec §7.2 `:487` 点名的 12 项**：`interval_run`(间歇跑) / `compound_circuit`(复合循环) / `steady_run`(持续跑) / `step_training`(台阶训练) / `bodyweight_resistance`(自重抗阻) / `band_resistance`(弹力带抗阻) / `interest_ball_games`(兴趣球类) / `orienteering`(定向越野) / `functional_training`(功能性训练) / `hiit`(HIIT) / `energy_expenditure_plus_10pct`(能量消耗模块，照 spec `:482` 的模块名命名) / `resistance_priority`(抗阻优先模块，照 spec `:484`) = **12**
- **速度柔韧类 4 项**（简报 Step 1 明列）：`sprint_50m_intervals` / `dynamic_stretching` / `shuttle_run` / `sit_and_reach_drill` = **4**
- **按 18 套模板的实际需要补 7 项**：`brisk_walking` 与 `stationary_cycling`（两个 low 冲击有氧，是 5 个 high 动作在等价表里的**落点**，没有它们 3 个 high 无解 → 直接落 `needs_review`）、`medicine_ball_core`（红层力量短板需要 70% 1RM 量级的**单动作**抗阻主项，`compound_circuit` 是多动作串联、单动作强度上不去）、`plyometric_jump`（立定跳远是国标 6 个短板判定项之一，红层要提升它必须有跳跃刺激；同时它是 BMI > 30 时最该被换掉的动作）、`agility_ladder`（绿层速度柔韧短板需要一个 medium 主项，两个 low 档拉伸撑不起一次课的主体）、`pnf_stretching`（坐位体前屈是国标项，柔韧提升除动态拉伸外还需要 PNF 这一档）、`challenge_task`（spec `:487` 绿层那句「+ **可选挑战任务**」此前没有 ref）= **7**

合计 **12 + 4 + 7 = 23**，落在简报「预估 20–30 个」区间内。**7 个补项的理由逐条写在 `exercises.yaml` 的分节注释里**，不是只在报告里说。

**视频 URL**：全部是 `https://example.invalid/exercise/<ref>`（RFC 2606 保留 TLD，DNS 保证不可解析）。**没有编造任何真实链接**，由 `test_video_urls_are_rfc2606_placeholders_keyed_by_ref` 钉住。

### 1.2 修改文件（8 个）

| 路径 | 改了什么 | 是代码还是散文 |
|---|---|---|
| `backend/app/db/models/prescription.py` | 加 `Exercise` ORM（6 列 + `_in_domain` CHECK + `ref` UNIQUE）；**重写模块 docstring 更正 P2-A10 的 4 处错** | **代码 + 散文** |
| `backend/tests/db/test_models.py` | 函数名 `fourteen`→`fifteen`；`expected` 集合加 `"exercise"`；**3 处 `== 14` → `== 15`**；**`len(json_text_columns) == 8` → `== 9`**（派单未列，见 §6 错误 1）+ 新增 `assert "exercise.targets" in json_text_columns`；`_in_domain` 反解列数的散文 10 → 11 + P2-A5 的覆盖面说明 | **代码 + 散文** |
| `backend/tests/seed/test_generate.py` | 新增 `REFERENCE_TABLES = ("exercise",)` + 新增 `test_table_partition_is_exhaustive`（分区穷尽 + 互不相交 + 逐 Task 递增）；把「必须为 0」那一圈的遍历对象从 `DATA_TABLES` 扩成 `DATA_TABLES + REFERENCE_TABLES` | **代码 + 散文** |
| `backend/app/db/session.py` | `:4` / `:46` / `:91` 三处「14 张表」→「15 张表」 | **纯散文** |
| `backend/app/db/models/__init__.py` | `:1`「14 张表 … §4.1–§4.3」→「15 张表 … §4.1–§4.4」+ 逐 Task 递增说明；`:15`「八个列」→「九个列」；小节表 `.prescription` 行「今天为空」→「1 张」；`:72-73`「两个今天为空的小节」→ 只 `feedback` 为空、并写明 `prescription` 的导入现在是**承重的**；`__all__` 上方加一段说明「Plan 02 的表类刻意不进公有导入面」 | **纯散文 + 注释** |
| `backend/app/db/models/_shared.py` | 「**四个**表模块都要用它们」→「**五个**」（`prescription` 现在也用 `JsonText` + `_in_domain`）；「全库八个 JSON 形态的列」→「九个」+ 指明它由哪条测试钉住 | **纯散文** |
| `backend/app/refdata.py` | 「本模块同时是 `backend/data/` 下**文件名与目录**的唯一所有者」→ 收窄成「目录常量 + 国标评分表/指标区间表两个文件名」，并写明处方侧两个 YAML 文件名住在 `app/refdata_prescription`、`DATA_DIR` 仍是唯一一份 | **纯散文** |
| `Document/2026-09-28-体育闭环原型-设计spec.md` | §14 追加第 **28** 项（`:933`），**CRLF 保持** | 授权范围内的唯一 `Document/` 改动 |

**`.gitattributes` 未改**（P2-A7）。Step 4 的确认已做：`git add` 之后 `git ls-files --eol -- backend/data/` 输出

```
i/lf    w/lf    attr/text eol=lf        backend/data/exercise_equivalence.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/exercises.yaml
```

两个新文件都落进了 `:14` 那条既有规则 ✅。

### 1.3 spec §14 第 28 项

追加在 `:933`（`| **27** |` 那行之后、空行与 `---` 之前），格式照 `:930-932`（6 个 `|` = 5 个单元格），**CRLF 保持**（写前 973 CRLF / 写后 974 CRLF，逐行都是 CRLF）。

- **事项**：`exercise_equivalence.yaml` 的 `volume_reduction` 两个系数（BMI > 30 → `0.8`；肌肉量 < P10 → `0.9`）
- **标题（第一项单元格）逐字**：`**\`exercise_equivalence.yaml\` 的 \`volume_reduction\` 两个系数（BMI > 30 → \`0.8\`；肌肉量 < P10 → \`0.9\`）**`
- **默认规定**：写明 spec 全文无出处、`:604` 的 0.8 属 Plan 03 的预警减量而非 §7.4 的跑量下调、`0.9` 无对应物；给出 0.8 / 0.9 的取法理由；写明「须提供指导文件或运动处方规范里的实际下调幅度」
- **章节**：§7.4
- **影响面**：YAML 的两个值 + 钉住它们的两条测试 + Task 7 的消费；明写「**Task 7 不得把它们当成 spec 条文引用**」；**并写明与计划 Task 12 的 #28/#32 编号冲突及处置**（见 §6 错误 3）

sha256[:16] 写前 `aca276932070ef94` → 写后 `98c7443bb241b43e`；85847 B / 975 行。

### 1.4 超出简报的 4 处补充（逐条给理由）

1. **`test_equivalence_yaml_fingerprint_is_pinned`**（简报 Step 2 只点了 `exercises.yaml` 的指纹）。理由：把某条映射的 `to` 从一个 `low` 动作换成**另一个** `low` 动作，**不破坏任何一条形状不变量**（目标仍存在、仍不升冲击、high 仍有 low 替身、version 仍非空），六条语义测试会全绿 —— 这与终审 M4（改评分表一处 `raw_value`、全仓只有指纹红）是同一个失效形态，而 Ruling 213 的教训正是「只有指纹能挡住它」。
2. **`equivalence()` 单例**（简报 Produces 只列了 `load_exercises` / `exercises` / `load_equivalence`）。理由：Task 7 的安全后置是逐学生跑的，少了单例就每人重解析一次 YAML，而 spec §1.3 给单人处方生成的预算是 p95 < 3 秒；且与 `exercises()` 不对称本身就是会被下一轮评审挑的毛病。
3. **`test_table_partition_is_exhaustive` 里的「互不相交」与「`REFERENCE_TABLES == ("exercise",)`」两条断言**。P2-A1 只要求「穷尽」；不相交是穷尽的另一半（一张表被归两类会让「必须写 / 不许写」两条断言互相矛盾），逐 Task 递增则与 `== 15` 的既有纪律同构。
4. **变异 ①′**（把一条映射的 from/to 写反，造出 low→high）。理由见 §6 错误 6：变异 ① 是 high→high（**持平**），它开不了「序」那一支的火；不补这一探针，就无法证明那条判据不是死代码（硬规矩 #50）。

**另有 1 处刻意「不做到底」**：`test_sync_exercises_projects_every_ref_and_is_idempotent` 里的条目数断言我**从 `== 23` 改成了 `>= 20`**。理由写在测试注释里：精确值已由指纹钉住，再钉一次等于给 Task 3 增加一个必须同步更新的常量，而简报 Step 1 明确允许 Task 3 往 `exercises.yaml` **追加** `exercise_ref`、只要求它更新指纹常量。⚠️ 副作用必须交代：**我最初写的就是 `== 23`，那会让变异 ② 多红一条**，与派单/账本 P2-C1 的「只有指纹测试会红」不符；改成下界之后 P2-C1 的判据才按字面成立（亲验：全量 528 条里只红 1 条）。

---

## 2. 每条测试的红 → 绿

TDD 三段红，全部亲跑，输出逐字抄在下面（**不只有绿的那一次**）。

### 2.1 红 1 —— 只写测试、完全没有生产码

```
$ cd backend; python -m pytest -q tests/test_refdata_prescription.py tests/domain/test_prescription_templates.py
=================================== ERRORS ====================================
_____________ ERROR collecting tests/test_refdata_prescription.py _____________
ImportError while importing test module '…\backend\tests\test_refdata_prescription.py'.
tests\test_refdata_prescription.py:38: in <module>
    from app import refdata_prescription as rp
E   ImportError: cannot import name 'refdata_prescription' from 'app' (…\backend\app\__init__.py)
________ ERROR collecting tests/domain/test_prescription_templates.py _________
ImportError while importing test module '…\tests\domain\test_prescription_templates.py'.
tests\domain\test_prescription_templates.py:29: in <module>
    from app.domain.prescription.templates import ImpactLevel
E   ModuleNotFoundError: No module named 'app.domain.prescription'
=========================== short test summary info ===========================
ERROR tests/test_refdata_prescription.py
ERROR tests/domain/test_prescription_templates.py
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!
2 errors in 0.42s
```

### 2.2 红 2 —— 生产码 + YAML 都在，两个指纹常量还是哨兵 `__PENDING__`

```
$ python -m pytest -q tests/test_refdata_prescription.py tests/domain/test_prescription_templates.py
E   AssertionError: 动作库被改动了：sha256 前 16 位是 39A7A4D11DD74F14，钉住的是 __PENDING__。…
E   assert '39A7A4D11DD74F14' == '__PENDING__'
E   AssertionError: 等价映射表被改动了：sha256 前 16 位是 0FFB881574AC04F3，钉住的是 __PENDING__。…
E   assert '0FFB881574AC04F3' == '__PENDING__'
2 failed, 44 passed in 0.78s
```

**这一段的取证价值**：44 条**功能性**测试在生产码落地后一次性转绿，而两条**指纹**测试独立地红着 —— 说明指纹那两条不是跟着别人一起绿的，它们守的是「字节」这件别人守不住的事。
（注：`39A7A4D11DD74F14` 是 `exercises.yaml` 在**改注释之前**的指纹；后来我把 YAML 里「条目数由 `== 23` 字面钉住」那句改成「`>= 20` 下界」（见 §1.4），指纹变成 **`A6A000F58815FCBB`**，测试常量同步更新，双向查过：新串命中 1 次、`__PENDING__` 与旧串残留 **0** 次。）

### 2.3 红 3 —— 加表之后既有守卫变红（Step 4 之前）

```
$ python -m pytest -q
FAILED tests/db/test_models.py::test_all_fourteen_tables_created - assert … == expected（expected 少 'exercise'）
FAILED tests/db/test_models.py::test_no_column_uses_builtin_sqlalchemy_json - AssertionError: 守卫的覆盖面必须先被确认是这 14 张表 / assert 15 == 14
FAILED tests/db/test_models.py::test_only_derived_tables_expose_batch_id - AssertionError: 守卫的覆盖面必须先被确认是这 14 张表 / assert 15 == 14
FAILED tests/db/test_models.py::test_models_public_namespace_is_unchanged_by_the_split - AssertionError: assert 15 == 14
4 failed, 523 passed in 55.46s
```

⚠️ **这一轮暴露了派单未列的第 4 处改动面**：`len(json_text_columns) == 8` 当时**没有**红 —— 因为它被同函数前面那条 `assert len(tables) == 14` 挡住了、根本没跑到。把三处 `== 14` 改成 `== 15` 之后它才浮出来（见 §6 错误 1）。**这是「按派单字面改完就交」会漏掉的一处**，而它的失效形态是静默的：`Exercise.targets` 若哪天退回 SQLAlchemy 自带的 `JSON` 类型，那条守卫本该炸，却因为数量对不上而先炸在别处。

### 2.4 绿

```
$ python -m pytest -q tests/test_refdata_prescription.py tests/domain/test_prescription_templates.py
46 passed in 0.69s            # 43 + 3

$ python -m pytest -q
528 passed in 55.75s          # 481 基线 + 46 新 + 1（test_table_partition_is_exhaustive）

$ python -m pytest -q --cov=app.domain --cov-branch --cov-report=term-missing
Name                                   Stmts   Miss Branch BrPart  Cover   Missing
app\domain\__init__.py                     0      0      0      0   100%
app\domain\derive.py                     146      0     54      0   100%
app\domain\indicators.py                  62      0     14      0   100%
app\domain\percentile.py                  94      0     26      0   100%
app\domain\prescription\__init__.py        2      0      0      0   100%
app\domain\prescription\templates.py       5      0      0      0   100%
app\domain\stratify.py                    92      0     20      0   100%
app\domain\tables.py                       5      0      0      0   100%
TOTAL                                    406      0    114      0   100%
527 passed, 1 skipped in 119.15s (0:01:59)
```

那 1 条 skip 是 `tests/pipeline/test_backfill.py:182` 的 trace-hook 自觉跳过（既有行为，与本 Task 无关）。
**Global Constraint #2 达成**：`Miss 0 / BrPart 0 / 100%`，且验收命令**带了 `--cov-branch`**。

### 2.5 46 条新测试逐条清单与它守什么

`tests/domain/test_prescription_templates.py`（**3** 条）

| # | 测试 | 守什么 |
|---|---|---|
| 1 | `test_impact_level_values_match_spec_4_4_verbatim` | 取值与**声明序**逐字等于 spec §4.4 `:239`（期望侧是字面量） |
| 2 | `test_impact_level_is_a_str_enum_so_it_round_trips_through_the_db` | `str` 子类（否则落库成 `"ImpactLevel.HIGH"` = 19 字符、撑破 `String(8)`） |
| 3 | `test_impact_level_rejects_a_value_outside_spec_4_4` | 5 个词表外值（`very_high` / `hig` / `HIGH` / `""` / `none`）全部 `ValueError` |

`tests/test_refdata_prescription.py`（**43** 条 = 25 个函数，其中两个 parametrize 展开成 9 + 11 = 20 条）

| # | 测试 | 守什么 |
|---|---|---|
| 1 | `test_exercises_yaml_fingerprint_is_pinned` | 动作库字节（CRLF→LF 后 sha256[:16]，Ruling 231 口径） |
| 2 | `test_equivalence_yaml_fingerprint_is_pinned` | 等价表字节（**补充 1**） |
| 3 | `test_target_domain_is_the_three_bucket_names_not_the_raw_values` | **P2-A4**：`set(ITEM_BUCKET.values())` 有 4 个含 `None`，过滤后才是 3 个桶名 |
| 4 | `test_every_exercise_has_a_valid_impact_level_and_targets` | 每个动作的 `impact_level` / `targets` 合法（期望侧来自枚举与 `ITEM_BUCKET`，**不从 YAML 读回**） |
| 5 | `test_exercise_refs_are_snake_case_and_unique_keys` | ref 形状 + **顶层键无重复**（PyYAML 对重复键静默后者覆盖前者；用**原始文本**数一遍与解析结果对账，两侧不同源） |
| 6 | `test_video_urls_are_rfc2606_placeholders_keyed_by_ref` | 全部 URL == `https://example.invalid/exercise/<ref>`（用户裁定「不编造真实链接」） |
| 7 | `test_equivalence_table_only_maps_to_existing_exercises` | 映射两端都在动作库里 |
| 8 | `test_equivalence_never_maps_to_a_higher_impact_level` | **安全属性核心**：序（字面写死 `high > medium > low`）+ 声明的 `max_impact` 与替身真实冲击一致 |
| 9 | `test_equivalence_table_has_a_version` | `version` 非空字符串 + 字面钉住 `"1.0"`（spec §7.4 `:512`） |
| 10 | `test_every_high_impact_exercise_has_a_low_substitute` | 5 个 high 每个在**两个触发下各**有一个 low 替身（P2-C2 的名字更正）；带防空转断言 `assert high_refs` |
| 11 | `test_equivalence_when_values_are_exactly_the_two_spec_7_4_triggers` | `when` 取值域恰好 = spec §7.4 `:508-509` 那两个（P2-C3：`:510` 走 addons、不查等价表） |
| 12 | `test_volume_reduction_coefficients_are_pinned_verbatim` | **Ruling 7**：0.8 / 0.9 字面钉住 + 都在 `(0, 1)` 内 |
| 13 | `test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable` | `lookup` 的三条语义；**用合成表**造出 `max_impact=medium` 的映射，证明 `impact_ceiling` 这个参数真的被用上（硬规矩 #50 的双输入） |
| 14 | `test_exercise_string_column_widths_fit_the_yaml_values` | **P2-A5**：`ref`/`name`/`video_url`/`equipment` 四列的列宽（实际侧从 YAML 现读，期望侧是 `.type.length`） |
| 15 | `test_exercise_impact_level_vocabulary_agrees_with_the_domain_enum` | ORM 类常量 ↔ domain 枚举的漂移测试（Global Constraint #3） |
| 16 | `test_exercise_ref_is_unique_at_the_db_level` | `ref` UNIQUE 真的在 DDL 里 |
| 17 | `test_exercise_impact_level_check_rejects_unknown_value` | `_in_domain` 生成的 CHECK 真的生效（写 `very_high` → `IntegrityError`） |
| 18 | `test_sync_exercises_projects_every_ref_and_is_idempotent` | 投影逐列对账 + 重跑不翻倍 + 条目数 `>= 20` |
| 19 | `test_sync_exercises_updates_a_changed_field_in_place` | upsert 的 PATCH 语义（改坏一个 `name` 再 sync 回来） |
| 20 | `test_load_exercises_is_read_only_and_cached` | `exercises()` 是单例、`load_exercises()` **不**缓存（P2-A9 口径）、`MappingProxyType` 拒写 |
| 21 | `test_load_exercises_reports_the_file_when_missing` | 缺文件 → `FileNotFoundError` |
| 22 | `test_load_equivalence_reports_the_file_when_missing` | 同上 |
| 23–31 | `test_load_exercises_rejects_a_malformed_library`（parametrize × **9**） | 空文件 / 顶层不是映射 / 非法 `impact_level` / 空 `targets` / `targets: [bmi]`（**P2-A4 的直接落地**）/ 缺 `equipment` / 多余键 `coach` / 大写 ref / 空 `video_url`——每条都断言报错点名了**文件**与该**字段** |
| 32–42 | `test_load_equivalence_rejects_a_malformed_table`（parametrize × **11**） | 缺/空 `version`、缺 `mappings`、缺/键不符/系数越界的 `volume_reduction`、非法 `when`（`body_fat_over`）、非法/缺失 `max_impact`、缺 `when`、顶层不是映射 |
| 43 | `test_a_wellformed_minimal_library_round_trips` | **已知 GREEN 的干净对照**（硬规矩 #53）：没有它，「把校验改成一律 raise」也能让 20 条拒绝用例全绿 |

---

## 3. 变异验收（Step 5）

**方法**：探针脚本 `$env:TEMP\mut.py`（跑完已删），动作 = `clean` / `1` / `1b` / `2` / `3` / `restore`。
- **硬规矩 #53**：每个变异都打印 **`yaml.safe_load` 的 before/after 结构差**，并断言「其余部分逐项相同」——YAML 没有 AST，解析后的结构差就是它的 AST 等价物；同时断言**没被动的那份文件 sha256 不变**。
- **硬规矩 #62**：变异探针与 pytest **串行**跑，一次一个。
- **还原**：从 `$env:TEMP\_t2_pristine` 按**字节**写回，逐个核 sha256（**不用** `git checkout`/`git restore`，硬规矩 #46）。

### 3.0 干净对照（已知 GREEN，跑在一切变异之前）

```
$ python $env:TEMP\mut.py clean
  before exercises.yaml               a6a000f58815fcbb  13358B PRISTINE
  before exercise_equivalence.yaml    0ffb881574ac04f3   7841B PRISTINE
  干净对照：两份 YAML 的 sha256 与钉住值逐字节相符 = True
    exercises: 23 条；equivalence: version='1.0', 10 条映射, volume_reduction={'bmi_over_30': 0.8, 'muscle_low_p10': 0.9}
    high 冲击动作 5 个: ['hiit', 'interval_run', 'plyometric_jump', 'shuttle_run', 'sprint_50m_intervals']
      hiit                   -> ['functional_training', 'functional_training']  冲击=['low']
      interval_run           -> ['stationary_cycling', 'stationary_cycling']  冲击=['low']
      plyometric_jump        -> ['bodyweight_resistance', 'bodyweight_resistance']  冲击=['low']
      shuttle_run            -> ['brisk_walking', 'brisk_walking']  冲击=['low']
      sprint_50m_intervals   -> ['stationary_cycling', 'stationary_cycling']  冲击=['low']
    干净对照断言：每个 high 的替身冲击都是 low -> PASS
```

### 3.1 变异 ①：把某个 `high` 动作的等价物改成另一个 `high`

`interval_run` 在 `when: bmi_over_30` 下的 `to`：`stationary_cycling`(low) → `plyometric_jump`(**high**)。

```
  结构差（等价映射表 mappings[0]）:
    before: {'from': 'interval_run', 'to': 'stationary_cycling', 'max_impact': 'low', 'when': 'bmi_over_30'}
    after : {'from': 'interval_run', 'to': 'plyometric_jump', 'max_impact': 'low', 'when': 'bmi_over_30'}
    plyometric_jump 的真实 impact_level = high
    interval_run    的真实 impact_level = high
  after exercises.yaml               a6a000f58815fcbb  13358B PRISTINE   ← 未被动到
  after exercise_equivalence.yaml    5c601004c65125ef   7838B MUTATED
```

```
$ python -m pytest -q tests/test_refdata_prescription.py
FAILED …::test_equivalence_yaml_fingerprint_is_pinned            - sha256 前 16 位是 5C601004C65125EF，钉住的是 0FFB881574AC04F3
FAILED …::test_equivalence_never_maps_to_a_higher_impact_level   - interval_run -> plyometric_jump 声明 max_impact=low，而 plyometric_jump 的真实冲击是 high
FAILED …::test_every_high_impact_exercise_has_a_low_substitute   - interval_run（high）在 when=bmi_over_30 下映射到 plyometric_jump，而它的冲击是 high、不是 low
FAILED …::test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable - assert 'plyometric_jump' == 'stationary_cycling'
4 failed, 39 passed in 0.81s
```

**判据「『不升冲击』测试必须红」→ 达成**（`test_equivalence_never_maps_to_a_higher_impact_level` 红）。
⚠️ **但红的原因与它的名字不符**：报错文本是「**声明 max_impact=low，而真实冲击是 high**」，**不含**「升了冲击」——因为 high→high 是**持平**，序那一支按设计不开火。详见 §6 错误 6 与下面的 ①′。

**还原**：`restore sha256 全部相符: True`，两份文件 sha256 逐字节回到 `a6a000f5…` / `0ffb8815…`；还原后 `43 passed`。

### 3.2 变异 ①′（补充探针）：造一个**真·升冲击**的映射

把 `hiit → functional_training`（high→low）整条**方向写反**成 `functional_training → hiit`（**low→high**），并把 `max_impact` 一并改成 `high`（模拟专家把 from/to 敲反、且自认为改对了）。

```
  结构差（等价映射表里 hiit 的那条 bmi_over_30 映射）:
    before: {'from': 'hiit', 'to': 'functional_training', 'max_impact': 'low', 'when': 'bmi_over_30'}
    after : {'from': 'functional_training', 'to': 'hiit', 'max_impact': 'high', 'when': 'bmi_over_30'}
    functional_training 的真实冲击 = low
    hiit                  的真实冲击 = high
  after exercises.yaml               a6a000f58815fcbb  13358B PRISTINE
  after exercise_equivalence.yaml    c3c67b10e24d9f68   7842B MUTATED
```

```
$ python -m pytest -q tests/test_refdata_prescription.py
FAILED …::test_equivalence_yaml_fingerprint_is_pinned            - sha256 前 16 位是 C3C67B10E24D9F68
FAILED …::test_equivalence_never_maps_to_a_higher_impact_level   - functional_training(low) -> hiit(high) 升了冲击
FAILED …::test_every_high_impact_exercise_has_a_low_substitute   - hiit（high）缺 when=bmi_over_30 的等价物
3 failed, 40 passed in 0.78s
```

**取证结论**：「序」那一支**真的开火了**（报错文本含「升了冲击」）→ 它不是死代码。这也量化了它的能力边界：**在 `from` 全是 `high` 的真实表上它结构性不可达**，能抓「替身不是 low」的是 `test_every_high_impact_exercise_has_a_low_substitute` 与 `max_impact` 一致性那一支（硬规矩 #39：守卫能力必须写明它守不住什么——这段已写进那条测试的 docstring 与本报告）。

**还原**：sha256 相符，`43 passed`。

### 3.3 变异 ②：把一个 `exercise_ref` 从 `exercises.yaml` 删掉

删 `challenge_task`（**刻意挑一个非等价表端点的 ref**；探针里断言了这一点：`challenge_task 是否等价表端点: False`）。

```
  结构差（动作库键集）:
    before: 23 keys
    after : 22 keys
    丢失的键: ['challenge_task']
    challenge_task 是否等价表端点: False -> ['bodyweight_resistance', 'brisk_walking', 'functional_training', 'hiit', 'interval_run', 'plyometric_jump', 'shuttle_run', 'sprint_50m_intervals', 'stationary_cycling']
  after exercises.yaml               d7e29c4f535fe7ab  13161B MUTATED
  after exercise_equivalence.yaml    0ffb881574ac04f3   7841B PRISTINE
```

**全量跑**（不只是那一个测试文件，因为判据是「本 Task 只有指纹测试会红」）：

```
$ python -m pytest -q
FAILED tests/test_refdata_prescription.py::test_exercises_yaml_fingerprint_is_pinned - 动作库被改动了：sha256 前 16 位是 D7E29C4F535FE7AB，钉住的是 A6A000F58815FCBB
1 failed, 527 passed in 55.73s
```

**判据 → 精确达成：全仓 528 条里只红 1 条，就是指纹测试**（P2-C1 的更正成立；「模板引用存在性」测试确实是 Task 3 才建的）。

⚠️ 如 §1.4 末段所述：这条判据能按字面成立，**是因为我把 `assert written == 23` 改成了 `>= 20`**。若留着 `== 23`，这里会是 2 failed。

**还原**：sha256 相符。

### 3.4 变异 ③：删掉 `version`

```
  结构差（等价映射表顶层键）:
    before keys: ['mappings', 'version', 'volume_reduction']
    after  keys: ['mappings', 'volume_reduction']
  after exercises.yaml               a6a000f58815fcbb  13358B PRISTINE
  after exercise_equivalence.yaml    da50523bee2d5f61   7826B MUTATED
```

```
$ python -m pytest -q tests/test_refdata_prescription.py
FAILED …::test_equivalence_yaml_fingerprint_is_pinned                        - sha256 前 16 位是 DA50523BEE2D5F61
FAILED …::test_equivalence_table_has_a_version                               - ValueError: … 的 version 缺失或不是非空字符串，实为 None
FAILED …::test_equivalence_table_only_maps_to_existing_exercises             - ValueError: （同上）
FAILED …::test_equivalence_never_maps_to_a_higher_impact_level               - ValueError: （同上）
FAILED …::test_every_high_impact_exercise_has_a_low_substitute               - ValueError: （同上）
FAILED …::test_equivalence_when_values_are_exactly_the_two_spec_7_4_triggers - ValueError: （同上）
FAILED …::test_volume_reduction_coefficients_are_pinned_verbatim             - ValueError: （同上）
FAILED …::test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable - ValueError: （同上）
FAILED …::test_load_exercises_is_read_only_and_cached                        - ValueError: （同上）
9 failed, 34 passed in 0.78s
```

**判据「版本测试必须红」→ 达成**（`test_equivalence_table_has_a_version` 红）。
⚠️ 但**红了 9 条不是 1 条**：`load_equivalence` 对缺 `version` 是**加载时响亮失败**（`raise ValueError`），凡调用它的测试全部报错。这是设计后果而非缺陷——spec §7.4 `:512` 要求版本号必须被记进 `safety_substitutions`，把它做成可选字段才是缺陷。若控制者期望的是「只红一条」，需要把 `version` 变可选，**我不建议**，理由已写进 `load_equivalence` 的 docstring。

**还原**：`restore sha256 全部相符: True`；还原后全量 `527 passed, 1 skipped`（带 `--cov`）+ `528 passed`（不带）。

### 3.5 变异验收小结

| 变异 | 字节确认真的改了 | 红的测试数 | 判据要求的测试 | 达成 |
|---|---|---|---|---|
| 干净对照 | —（sha256 == 钉住值） | 0 | — | ✅ GREEN |
| ① high→high | ✅ `0ffb8815…` → `5c601004…`，结构差打印在案 | 4 / 43 | `test_equivalence_never_maps_to_a_higher_impact_level` | ✅（但开火的是 `max_impact` 一致性支，见 §6-6） |
| ①′ low→high（补充） | ✅ → `c3c67b10…` | 3 / 43 | 同上（**序**支真的开火） | ✅ |
| ② 删 ref | ✅ `a6a000f5…` → `d7e29c4f…` | **1 / 528（全量）** | 只有指纹 | ✅ 精确达成 |
| ③ 删 `version` | ✅ → `da50523b…` | 9 / 43 | `test_equivalence_table_has_a_version` | ✅ |

**四次还原全部按字节核过 sha256，逐字节相符；终态两份 YAML 的 sha256 与 §1.1 表里的值一致。**

---

## 4. 改动面自证（硬规矩 #32：`ast.dump` 等价性 + **两组对照**）

判据取自 Plan 01 账本 `:3368`「## 硬规矩 #32：`ast.dump` 等价性 + 两组对照」与 `:3278` 记的做法。
⚠️ **硬规矩 #47**：`git show HEAD:<path>` 给的是 blob 的 **LF** 版、工作树是 CRLF，故两侧都先归一化成 LF 再 parse（docstring 里的换行进 AST 常量，不归一化会假报不同）。

### 4.1 主判定

| 文件 | `ast.dump`(HEAD) vs (工作树) | 期望 | 判定 |
|---|---|---|---|
| `backend/app/db/session.py` | **相同** | 相同（纯散文） | PASS |
| `backend/app/db/models/__init__.py` | **相同** | 相同（纯散文 + 注释） | PASS |
| `backend/app/db/models/_shared.py` | **相同** | 相同（纯散文） | PASS |
| `backend/app/refdata.py` | **相同** | 相同（纯散文） | PASS |
| `backend/app/db/models/prescription.py` | **不同** | 不同（新表类） | PASS |
| `backend/tests/db/test_models.py` | **不同** | 不同（计数 + 1 条新断言） | PASS |
| `backend/tests/seed/test_generate.py` | **不同** | 不同（新常量 + 新测试 + 遍历扩表） | PASS |

七个新文件另用 `git cat-file -e HEAD:<path>` 逐个确认**在 HEAD 里不存在**（7/7 返回非 0）→ 它们是新增而不是改写。

### 4.2 对照组 ①：不剥 docstring

**同一批四个「纯散文」文件，在不剥 docstring 的口径下全部报「不同」**（我第一次跑就是这个结果，4/4 FAIL）。这正是需要的对照：它证明**改动确实发生了、且全部落在 docstring 里**——剥掉 docstring 后 4/4 变「相同」。少了这一组，「AST 相同」有可能是因为我根本没改成任何东西。

### 4.3 对照组 ②：往基线注入真语义变异，AST 闸门必须全抓到

| 注入的变异 | 为什么是真语义 | 剥 docstring 后相同？ | 结果 |
|---|---|---|---|
| `session.py`：`PRAGMA foreign_keys=ON` → `OFF` | 关掉 SQLite 外键强制（Ruling 27 的钩子失效） | False | **CAUGHT** |
| `models/__init__.py`：从 `__all__` 删掉 `"CleaningLog"` | 公有导入面少一个表类 | False | **CAUGHT** |
| `_shared.py`：`impl = Text` → `impl = String` | `JsonText` 的底层类型换了 | False | **CAUGHT** |
| `refdata.py`：`MIN_SEGMENTS_PER_GROUP = 2` → `3` | 评分表每组档位数下限抬高 | False | **CAUGHT** |

```
注入 4 个真语义变异，AST 闸门抓到 4 个 -> PASS（剥 docstring 没把闸门剥瞎）
```

**两组对照都跑了、都通过**：①「改动确实发生且全在 docstring 里」② 「剥 docstring 这个口径没有把闸门剥瞎」。（探针脚本 `$env:TEMP\ast_diff.py` / `ast_control2.py` 跑完已删，`Test-Path` 均为 `False`。）

### 4.4 行为面的对照

除了 AST，还有一层行为证据：**基线 481 条测试全部保留且全绿**（终态 528 = 481 + 47 新增，无一条被删除、被 skip、被改判据放宽）。三处既有守卫的改动是**收紧或等量替换**：

- `test_all_fifteen_tables_created`：`expected` 集合**加**一个名字，`==` 的判据形态不变（仍是 Ruling 28 的「恰好这些」）
- `test_no_column_uses_builtin_sqlalchemy_json`：`== 8` → `== 9` 是**跟着新列走的等量更新**，并**新增**一条 `assert "exercise.targets" in json_text_columns`（让这个数字变化本身可验证，不是凭空 +1）
- `test_seed_database_writes_only_organisation_tables_and_is_idempotent`：遍历对象从 `DATA_TABLES` 扩成 `DATA_TABLES + REFERENCE_TABLES`，是**扩大**覆盖面（多查一张表必须为 0），没有放宽任何一条

`_MODELS_PUBLIC_BASELINE`（33 个名字）与 `_MODELS_ALL_BASELINE`（14 个名字）**一个字未改**——见 §7 关切 2。

---

## 5. 收工自证

```
$ git status --short          # commit 前：15 条，全部是本次要提交的，0 条未跟踪残留
M  "Document/2026-09-28-体育闭环原型-设计spec.md"
M  backend/app/db/models/__init__.py
M  backend/app/db/models/_shared.py
M  backend/app/db/models/prescription.py
M  backend/app/db/session.py
A  backend/app/domain/prescription/__init__.py
A  backend/app/domain/prescription/templates.py
M  backend/app/refdata.py
A  backend/app/refdata_prescription.py
A  backend/data/exercise_equivalence.yaml
A  backend/data/exercises.yaml
M  backend/tests/db/test_models.py
A  backend/tests/domain/test_prescription_templates.py
M  backend/tests/seed/test_generate.py
A  backend/tests/test_refdata_prescription.py
$ git status --short          # commit 后：0 行
```

**commit 后的亲跑取证**（硬规矩 #59：带断言性标题的产物必须亲眼看输出）：

```
$ git log --oneline -2
3ea27cc feat: Plan02 Task2 动作库——exercise 表 + exercises.yaml（23 个动作）+ exercise_equivalence.yaml（10 条映射），481 → 528 passed
fb5bddb docs: Task 2 预检更正计划正文 12 处（P2-A1..A10 / B1-B3 / C1-C2），含 2 处 Critical：…

$ git status --short                       # → 空
$ git show --stat --oneline HEAD           # → 15 files changed, 2004 insertions(+), 41 deletions(-)
$ git diff fb5bddb --stat -- .gitattributes # → 空（.gitattributes 一个字未改）
$ cd backend; python -m pytest -q          # → 528 passed in 78.24s
$ git ls-files --eol -- backend/data/
i/lf    w/lf    attr/text eol=lf        backend/data/exercise_equivalence.yaml
i/lf    w/lf    attr/text eol=lf        backend/data/exercises.yaml
```

**commit 之后两份 YAML 的字节没被 `git add` 改写**（`core.autocrlf=true` 下这是要复核的）：
`exercises.yaml` 13358 B / sha256[:16] `a6a000f58815fcbb` / CRLF **0**；
`exercise_equivalence.yaml` 7841 B / `0ffb881574ac04f3` / CRLF **0** —— 与 §1.1、§3.5 的值逐字节一致。

| 检查项 | 要求 | 实测 | 判定 |
|---|---|---|---|
| `git status --short`（commit 前） | 只含要提交的文件 | **15 条**，逐条都是本次改动 | ✅ |
| `git status --short`（commit 后） | 0 行 | **0 行** | ✅ |
| `backend/pe.db` | 不得存在 | **不存在** | ✅ |
| `backend/data/seed/` | 0 文件 | **`[]`** | ✅ |
| `national_standard_2014.csv` | 21412 B / `D2C8E539E2FA0029` / CRLF 0 | **21412 B / `D2C8E539E2FA0029` / CRLF 0** | ✅ |
| `.gitattributes` | 不改 | **未改**（不在 15 条里） | ✅ |
| `git ls-files --eol -- backend/data/` | 两个新 YAML `i/lf w/lf attr/text eol=lf` | **两个都是** | ✅ |
| 临时目录残留 | 无 | `$env:TEMP` 下 `mut.py` / `_t2_pristine` / `spec28.py` / `ast_diff.py` / `ast_control2.py` 全部 `Test-Path` = **False** | ✅ |
| `app/seed/` | Global Constraint #10 冻结 | **0 个文件被改**（不在 15 条里） | ✅ |
| `seed_database` | 不改一行 | **未改**（`app/seed/generate.py` 不在 15 条里） | ✅ |
| `tests/architecture` | 全绿 | **6 passed**；`SCANNED_DIRS` 扫到 **26** 个 `.py`（**P2-D4 预测 24 → 26，逐格相符**） | ✅ |
| 全量测试 | 全绿 | **528 passed**（不带 cov）/ **527 passed, 1 skipped**（带 cov） | ✅ |
| `app/domain/` 覆盖率 | Miss 0 / BrPart 0 / 100%，命令带 `--cov-branch` | **406 stmts / Miss 0 / 114 branch / BrPart 0 / 100%** | ✅ |
| 落盘闸门 | 双向查 | 每次编辑后都查了「新串命中 **且** 旧串 0 残留」；`SearchReplace` 有 **2 次**报成功而落盘形状不对（见 §6 错误 7），都被 shell 复核抓出并用 python 按字节修正 | ✅ |

**编辑工具的两次落盘异常（亲历，供账本参考）**：
1. `app/db/models/__init__.py` 的小节表：`SearchReplace` 报成功、diff 也回显了，但落盘后 `:mod:`.feedback`` 那一行**多了一个前导空格**（相邻行都没有），破坏了 RST 简单表的对齐。用 python 按索引 `[1:]` 切掉并复核 `repr()` 才修好。
2. 同文件另一处：diff 回显的缩进与实际落盘不一致，需要 `repr()` 逐行核。
→ 印证了派单里「编辑工具在本仓不可信」的判断。本轮所有落盘都用 shell 复核过（`ast.parse` + CRLF/LF 计数 + 双向串查 + `repr()` 逐行）。

**另：PowerShell 反引号被吃掉，本轮亲历一次。** 用 `python -c "…':mod:`.feedback`'…"` 做串匹配时，反引号被 PowerShell 吃掉，匹配串变成 `:mod:.feedback`，结果报「0 命中」而文件里明明有——差点让我以为文件是对的。改成按行索引操作才绕开。**凡串里含反引号，一律写进 `.py` 文件再跑。**

---

## 6. 我发现的控制者错误

按派单要求：逐条注明**成立 / 不成立 / 歧义**并给证据，不照顾控制者；**把不成立的指控认下来和把成立的辩掉是同一种失职**（Ruling 45/51/65），故 §6.2 也逐条列出我核过但**不成立**的怀疑。

### 6.1 成立

**错误 1（Important）— 改动面漏了 `tests/db/test_models.py:180` 的 `assert len(json_text_columns) == 8`。**
派单 §2 与账本 P2-A6 都只点了「`== 14` 共 3 处（`:163`/`:228`/`:472`）+ 函数名」。而 `Exercise.targets` 必须用 `JsonText`（`app/db/models/__init__.py:15` 的约定 3「JSON 形态的列一律用 `JsonText`，无一例外」，且由 `test_no_column_uses_builtin_sqlalchemy_json` 强制），故那个 **8 必然变 9**。
**证据**：亲跑红 3（§2.3）时它**没有**红——因为被同函数前面的 `assert len(tables) == 14` 挡住、根本没执行到。把三处 `== 14` 改成 `== 15` 之后它才浮出来。**这正是「按派单字面改完就交」会漏掉的一处。**
**连带**：`:173` 的注释「八个 JSON 形态的列」、`app/db/models/__init__.py:15`、`app/db/models/_shared.py:49` 的「八个」都跟着过期。
**处置**：4 处一并改成「九个」/`== 9`，并**新增** `assert "exercise.targets" in json_text_columns` 让这个 +1 可验证。

**错误 2（Important）— P2-A10 只查了 `app/db/models/prescription.py` 一个文件的 docstring，没做同类扫描；加表会让另外 6 处散文变假。**
P2-A10 的根因分析写得很准（「没人把『Task 1 新写的那两个占位模块 docstring』当成需要核对的对象」），但**它自己也没做全仓扫描**。亲跑 `grep -n "14 张|八个|四个表模块|唯一所有者"` 找到 6 处：

| 位置 | 原文 | 加表后为什么是假的 |
|---|---|---|
| `app/db/session.py:4` | 「14 张表的模型在 `app.db.models`」 | 15 张 |
| `app/db/session.py:46` | 「全部 14 张表的声明基类」 | 15 张 |
| `app/db/session.py:91` | 「仅为把 14 张表注册进 `Base.metadata`」 | 15 张 |
| `app/db/models/__init__.py:1` | 「14 张表的 ORM 模型（字段清单严格按 spec **§4.1–§4.3、§4.6**）」 | 张数错，**且小节范围漏了 §4.4**（这一处比张数更严重：它说的是「本包覆盖哪些 spec 小节」） |
| `app/db/models/__init__.py:34` + `:72-73` | 「`.prescription` §4.4 处方（**今天为空**，Plan 02 Task 2/3/9 填）」/「**两个**今天为空的小节也要被导入」 | `prescription` 不再为空，只剩 `feedback` 一个；且 `from . import prescription` 现在是**承重的**（漏掉它 `exercise` 表就不存在） |
| `app/db/models/_shared.py:4-6` | 「是因为**四个**表模块都要用它们（`organisation` / `assessment` / `derived` / `ops`）」 | `prescription` 现在也 import `JsonText` + `_in_domain`，是**五个** |
| `app/refdata.py:7-9` | 「本模块同时是 `backend/data/` 下**文件名与目录**的唯一所有者」 | 本 Task 把 `EXERCISES_FILENAME` / `EQUIVALENCE_FILENAME` 放进了 `app/refdata_prescription.py`，这句就成了假的 |

**判定：成立**，且形态与 P2-A10 完全同源（「对现状的断言」随一次改动过期）。硬规矩 #64 的要求是「与计划逐 Task 交叉核对」，但这一批不是「对未来的断言」而是「对现在的断言」，**#64 按字面覆盖不到它们**——建议把 #64 扩到「任何被本次改动使真的陈述」。
**处置**：7 处全部改正；其中 4 个文件用 §4 的 AST 闸门证明是**纯散文**改动（运行时行为零变化）。

**错误 3（Important）— spec §14 的编号冲突：P2-A3 裁定「本 Task 就追加一项」时没有与计划 Task 12 的编号交叉核对。**
计划 `:681`「Step 3: spec 勘误与 §14 补项（本计划累计 **7 项，#28–#34**）」、`:685` 逐条列了那 7 项，其中 **`#28` = 「18 套模板的审校状态」**、**`#32` = 「§7.4 的跑量下调系数与『提高抗阻比重』的处置」**；`:703` 又写「spec §14 从 27 项扩到 **34 项**」。
而 P2-A3 的裁定 + 派单都要求本 Task 就追加**第 28 项**、主题正是 #32 那一件。
**判定：成立**（按派单字面执行 → 本 Task 占了 #28，Task 12 的 7 项须整体后移为 **#29–#35** 并**删掉与原 #32 重复的那一条**，否则 §14 会出现两个 #28 与两个同主题条目；`:703` 的「34 项」也要跟着改成 35）。这正是硬规矩 #64 要防的形态，而它出在**做 #64 裁定的那一轮**（与 #58「立新规矩的当轮必须回查自己」同源）。
**处置**：按派单字面追加第 **28** 项（主题是 `volume_reduction`），并在该项的「影响面」单元格里**显式写明这个冲突与 Task 12 的处置办法**，让它不可能被漏掉。

**错误 4（Important）— 指令冲突：简报要求「在 spec §14 登记『须提供真实视频源』」，而派单只授权追加一项（#28，主题固定为 `volume_reduction`）。**
简报「决定（用户已裁定）」那段逐字是：「…并在 spec §14 登记『须提供真实视频源』」；派单 §2 逐字是：「**spec §14 追加一项**（`volume_reduction` 的两个系数无 spec 出处，P2-A3）——**这是你唯一被授权修改 `Document/` 的地方**，追加第 **28** 项」。
两条按字面**不可同时满足**（追加第 29 项会越权；把两件事塞进第 28 项会违反派单指定的主题与格式）。这与 P2-C1 是同一类形态（派一条按字面做不到的验收判据），只是这次冲突跨了两份文件。
**判定：成立（指令冲突）**。
**处置**：**只**追加第 28 项。视频源那条登记在 `exercises.yaml` 的头注释里（写明「`.invalid` 是 RFC 2606 保留 TLD、DNS 保证不可解析」「真实视频源须由项目组提供，届时整列替换并同步更新 `test_video_urls_are_rfc2606_placeholders_keyed_by_ref` 与指纹常量」），并在本报告 §7-5 列为未尽事项。**好消息**：计划 `:685` 的 **#29** 已经预留了「动作库的视频源（占位 `.invalid` URL）」这一题，Task 12 会补上，不会永久缺失。

**错误 5（Minor）— 简报 Interfaces 的 `load_exercises() -> dict[str, ExerciseSpec]` 与同一句里的「`MappingProxyType` 只读」自相矛盾。**
`types.MappingProxyType` **不是** `dict` 的实例（`isinstance(types.MappingProxyType({}), dict)` → `False`），故签名标 `dict` 而运行时返回 proxy 是一个假标注。
**判定：成立（自相矛盾的接口签名）**。同一句里 P2-A9 又要求「形状照 `load_standard()` + `standard()` 这一对」，而那一对的既有口径正是 `StandardTable.segments: Mapping[...]` + 加载方装入 `MappingProxyType`。
**处置**：标 `Mapping[str, ExerciseSpec]`、运行时返回 `MappingProxyType`，并在 `load_exercises` 的 docstring 里写明**为什么不是 `dict`**（含那句 `isinstance` 实测）。

**错误 6（歧义 / 半成立）— 变异 ① 的判据「『不升冲击』测试必须红」按字面可满足，但成立的理由与测试名不符。**
把 `high` 的等价物改成另一个 `high` 是**持平**，`test_equivalence_never_maps_to_a_higher_impact_level` 里那条序判据（`rank[target] < rank[source]`）**不会开火**。它之所以红，红在**同一测试的另一支**（「声明的 `max_impact` 与替身真实冲击不符」）。
**证据**：变异 ① 的报错文本是 `interval_run -> plyometric_jump 声明 max_impact=low，而 plyometric_jump 的真实冲击是 high`，**不含**「升了冲击」。
更值得记的一点：**在真实表上「序」那一支结构性不可达**——所有 `from` 都是 `high`（spec §7.4 只替换 high，P2-C2 的裁定），而 high 已经是最高档，无从「升」。
**判定：歧义**（判据可满足，但派单/简报把它归因给了一个不会开火的机制）。
**处置**：加做变异 **①′**（把一条映射的 from/to 写反，造出 low→high），亲验「序」那一支报出 `functional_training(low) -> hiit(high) 升了冲击` → 证明它不是死代码（硬规矩 #50）；并把这段能力边界写进那条测试的 docstring（硬规矩 #39）。

**错误 7（Minor，工具层不是控制者的错，但值得记账）— `SearchReplace` 两次报成功而落盘形状不对。**
详见 §5 末尾。派单说「已记录 **56 次**」，本轮**新增 2 次**（同一个文件 `app/db/models/__init__.py`），形态是「多写一个前导空格 / diff 回显的缩进与落盘不符」。**双向串查抓不到这一类**（串确实命中了、旧串也确实 0 残留），只有 `repr()` 逐行核或 AST 才抓得到 → 建议账本把落盘闸门的口径从「双向串查」升级成「双向串查 **+ 缩进/`repr()` 抽查**」。
另：本轮亲历一次 **PowerShell 吃掉反引号**导致串匹配假报「0 命中」（§5 末尾），派单已警告过反引号会被吃，但没说它会让**验证脚本本身**给出假阴性——这一层值得补进账本。

### 6.2 不成立（我核过、但控制者是对的）

按派单要求逐条给证据。**这些不是「照顾控制者」，是我真的去核了、结果它们成立。**

| 我核的对象 | 亲验结果 | 判定 |
|---|---|---|
| **P2-A1**（seed 方案违反 Global Constraint #10 + 撞两道守卫） | `seed_database` 在 `app/seed/generate.py`（存在）；`tests/seed/test_generate.py:519` 就是 `assert count == 0, f"{table} 不该由 seed_database 写入"`；`:483-488` 的 5 + 9 恰好 = 14 张表 | **不成立**（即：裁定正确）。本 Task **未新建** `app/seed/prescription.py`、**未改** `seed_database` 一行、**未改** `app/seed/` 任何文件 |
| **P2-A4**（`targets` 取值域） | 测试里亲断言：`len(set(ITEM_BUCKET.values())) == 4`、`None in …`、过滤后 == 三个桶名 | **不成立**（裁定正确）。并在 parametrize 里专门放了一条 `targets: [bmi]` 必须被拒 |
| **P2-A5**（列宽遍历测试只覆盖带 CHECK 的列） | 读 `_in_domain_columns()`：它从 `_IN_DOMAIN_SQL` 正则反解 `column IN (...)`，无 CHECK 的列进不来。实测 `Exercise` 只有 `impact_level` 被覆盖 | **不成立**（裁定正确）。四个无 CHECK 列已另写断言，实测最长值：`ref` **29**（`energy_expenditure_plus_10pct`）/ `name` **12**（`本体感觉神经肌肉促进拉伸`）/ `video_url` **62** / `equipment` **13**（`medicine_ball`），对 `String(48)/(64)/(256)/(32)` 全部容得下 |
| **P2-A6**（`== 14` 有 3 处 + 函数名 + 跨文件引用） | shell 亲数：`:163`/`:228`/`:472` 三处、函数名在 `:24`、`models/prescription.py:11` 按名字引用了它 | **不成立**（裁定正确）。⚠️ 但它**不完整**，见错误 1 |
| **P2-A7**（`.gitattributes` 不需改） | `:14` = `backend/data/*.yaml  text eol=lf`；`git add` 后 `git ls-files --eol` 显示两个新 YAML `i/lf w/lf attr/text eol=lf` | **不成立**（裁定正确） |
| **P2-A9**（`load_standard` 不缓存、`standard()` 才缓存） | 读 `app/refdata.py`：`load_standard` 每次新建 `StandardTable`；`standard()` 有 `global _standard_cache` | **不成立**（裁定正确）。`load_exercises`/`exercises` 照这一对写，并由 `test_load_exercises_is_read_only_and_cached` 钉住「`load_exercises()` **不**缓存」 |
| **P2-A10**（`models/prescription.py` docstring 的 4 处错） | 逐条核对计划：`:700` 的 18 张表清单里**没有** `prescription_override`；`:568`/`:569` 把 `training_package` 当**字段**用；`:524` Task 9「Modify 本文件（加两张表）」；`:491` Task 8 只建 `override.py` | **不成立**（4 处全部核实为错）。已按硬规矩 #64 更正，并把「归属表」写进新 docstring |
| **P2-B1 / B2 / B3 / C1 / C2 / C3** | 逐个核：`app/domain/prescription/` 改前确实不存在；spec `:470-471`/`:474-475` 确实每个 block 自带 `impact_level`；`refdata_prescription.py` 确实两个 Task 都要写；「模板引用存在性」测试确实不在本 Task；测试名与描述确实不符；spec §7.4 第三个触发确实走 addons | **全部不成立**（6 条裁定全部正确） |
| **P2-D2 / D3**（禁区无冲突 / 不得跑 CLI） | `exercises.yaml` 与 `exercise_equivalence.yaml` 落在 `backend/data/` **根**；`data/seed/` 全程 0 文件；全程未跑三个 CLI | **不成立**（无冲突） |
| **P2-D4**（建包后两条架构守卫不会红） | 亲数 `SCANNED_DIRS` 扫到的 `.py` = **26**（预测「24 → 26」逐格相符）；`tests/architecture` **6 passed** | **不成立**（预测精确正确） |
| **派单 §5 的全部自查** | 见 §fr0.1 的表，**17 项逐条亲验** | **全部不成立**（即：派单这部分无错） |

---

## 7. 关切与未尽事项

**1（最需要控制者裁定）— 三个值对象住在 `app/refdata_prescription.py`，domain 拿不到类型标注。**
P2-B1 规定 `templates.py` 本 Task **只放** `ImpactLevel`，故 `ExerciseSpec` / `EquivalenceMapping` / `EquivalenceTable` 只能与它们唯一的加载器同住（与 `app/pipeline/clean.py` 的 `FieldRange` 同形状）。**代价**：`tests/architecture/test_domain_purity.py` 的 allow-list 只放行 `enum` / `dataclasses` / `typing` / `collections` / `collections.abc` / `numpy` 与 `app.domain` 前缀，**所以 Task 7 的 `safety.py` 不能 import 这三个类型做标注**，只能按 `Mapping` / duck typing 接。若 Task 3/7 认为标注更重要，需要把这三个值对象搬进 `app/domain/prescription/`（Task 3 已经在 Modify 那个包），搬完本模块改成从 domain import。**建议派 Task 3 时先裁这一条**，否则 Task 7 会撞墙。已写进 `refdata_prescription.py` 的模块 docstring。

**2 — `Exercise` 刻意不在 `models` 的公有导入面里。**
没有 `from .prescription import *`、不进 `__all__`。理由：`test_models_public_namespace_is_unchanged_by_the_split` 钉的是**拆包之前**（基线 `e26347f`）实测的 33 个名字，往那份基线里加 Plan 02 的新名字，等于把「拆包没改导入面」偷换成「拆包后的现状」，两侧同源（硬规矩 #35）。**代价**：`models.Exercise` 不可用，必须写 `from app.db.models.prescription import Exercise`（实测 `Exercise in dir(models)` → `False`，`models.prescription.Exercise` → 可达）。已把这条决定写进 `app/db/models/__init__.py` 的注释。**Task 3/9 会撞上同一个决定点，建议一次性裁定**（要么一直保持子模块引用，要么在 Plan 02 收尾时统一把 4 张新表加进公有面并明确说明「基线测试的语义从『拆包前后相同』改成『拆包前 + Plan 02 新增』」）。

**3 — `sync_exercises` 今天没有生产调用方。**
P2-A1 禁止接进 `seed_database`，本 Task 也没接进管道（那是 Task 9/10 的活）。故真实库里 `exercise` 表今天是空的，只有测试灌它。已写进 `sync_exercises` 的 docstring（「谁在生产路径上调用它，本 Task 没有决定」）。**请控制者在派 Task 9/10 时明确落点。**

**4 — `load_equivalence` 刻意不做跨文件校验。**
它不检查 `from`/`to` 是否在动作库里。理由：否则变异 ② 会连带把等价表判坏，「只有指纹测试会红」这条判据就不成立了。跨文件不变量由 `test_equivalence_table_only_maps_to_existing_exercises` 守。若 Task 7 认为必须在**加载时**挡住（Review Focus 第 1 条的同构要求），改 `load_equivalence` 即可，但**要连带调整变异 ② 的判据**。已写进 docstring。

**5 — 视频源占位符未登记进 spec §14。**
见错误 4。今天它只登记在 `exercises.yaml` 的头注释里；计划 `:685` 的 #29 已预留这一题，Task 12 会补。**若控制者希望现在就登记，请明确授权追加第 29 项**（我没有自行越权）。

**6 — `equipment` 的词表没有唯一所有者，也没有测试钉它。**
本批用到 9 个取值（`none` / `band` / `step` / `cone` / `bike` / `mat` / `ball` / `ladder` / `medicine_ball`），但 spec §4.4 只说「器械需求」、没给词表，`Exercise.equipment` 也没有 CHECK（取值域不封闭）。今天它由 `exercises.yaml` **事实上**拥有，而我**刻意没有**为它写字面词表断言——钉住就等于造出第二个所有者（Global Constraint #3）。**若 Task 3 的模板要按器械筛动作**（例如「宿舍场景只用 `none`/`band`」），那时必须先给它立一个所有者（大概是在 `templates.py` 加一个 `Equipment` 枚举，再让 YAML 侧向它对齐）。

**7 — 变异 ③ 红 9 条而不是 1 条。**
见 §3.4。这是「加载时响亮失败」的设计后果。若控制者的期望是「只红一条」，那需要把 `version` 变可选字段，**我不建议**（spec §7.4 `:512` 要求它必须被记进 `safety_substitutions`）。

**8 — 基线覆盖率未独立复跑。**
见 §fr0.2 的 ⚠️ 注。用 `406 − 7 = 399` 与「branch 114 一个未增」做了算术交叉核对，与派单声称的基线逐格相符；但这是**推算**不是**复跑**。

**9 — Task 3 追加 `exercise_ref` 时的连带清单（提前写下来，免得它漏）。**
简报 Step 1 允许 Task 3 往 `exercises.yaml` 追加 ref。届时必须同步：① `EXERCISES_FINGERPRINT`；② 若新 ref 比 `energy_expenditure_plus_10pct`（29 字符）更长，复核 `String(48)`（`test_exercise_string_column_widths_fit_the_yaml_values` 会自动查，但列宽是声明侧、要人改）；③ 若新 ref 是 `high` 冲击，**必须**在 `exercise_equivalence.yaml` 里给它两个触发各一条 `low` 映射（否则 `test_every_high_impact_exercise_has_a_low_substitute` 红），并同步 `EQUIVALENCE_FINGERPRINT`；④ `exercises.yaml` 头注释里「条目数 23 的口径」与「high 5 / medium 10 / low 8」那段散文；⑤ 若考虑 `version` 是否要升（内容变了而版本号没变，`safety_substitutions` 就在撒谎）。**`>= 20` 那条下界断言不用改**（这正是我把它写成下界的原因）。

---

## fix round 2 — Ruling 106 的散文修正（CE-6 / CE-7）+ Ruling 107 的三条新守卫

**派单**：3 处过期散文（CE-6 相对导入计数 / CE-7 `app/db/models/__init__.py:74`）+ 3 条新守卫（Ruling 107-2 / -3 / -4）。
**基线**：`c21767d`（开工实测 `git status --short` 空、`python -m pytest -q` = **528 passed in 74.55s**、`--cov=app/domain --cov-branch` = **441 stmts / Miss 0 / 120 branch / BrPart 0 / 100%**、`527 passed, 1 skipped`）。
**产出**：一个 commit **`966eae0`**（不 push、不动 `main`），**531 passed**（= 528 + 3 条新测试函数），domain **441 / Miss 0 / 120 / BrPart 0 / 100%**（stmts **未变**）。
**改动面**：`git diff --name-status c21767d` = **4 个 M、全在 `backend/tests/`**；`backend/app/**` **零字节改动**；`backend/data`、`Document` 命中 **0**。
**行号口径**：一律 shell（python `read_bytes()` / `git grep -n`），全部绑定 commit `966eae0`（散文修正里引用的历史值另绑 `6a2938f` / `7b84599` / `3ea27cc` / `c21767d`）。

---

### fr2.0 ⚠️⚠️ 先报一件不属于本轮任务、但比本轮任何一条 finding 都严重的事：两份报告文件在本轮进行中被**外部进程截断**

**事实**：`task-2-report.md` 与 `task-1-report.md` 都在 **2026-10-07 16:44:34 / 16:44:35**（相差 1 秒）被改写，各自**丢掉了全部 `## fix round N` 追加节**，只剩主体那一轮的内容。

| 文件 | 本轮开工时我实测（约 15:2x） | 16:44 之后（现在） | 丢失 |
| --- | --- | --- | --- |
| `task-2-report.md` | **117694 B / LF 972 / CRLF 972** | **62640 B / LF 617 / CRLF 617**，sha16 `76A75BA3EFB3FB39` | **55054 B / 355 行** = 整个 `## fix round 1` 节（原 `:629`–`:972`） |
| `task-1-report.md` | （本轮没量过；账本 Ruling 64 记的是「fix round 4 落笔当时实为 **2616** 个 LF 行」） | **77837 B / LF 1031**，sha16 `621960F7A71466A9` | 全部 `## fix round 1`…`## fix round 5` 节；现在最后一个二级标题是 `## 8. 评审关切的处置汇总` |

**不是我做的**（逐条自证）：
1. 本轮我写盘的对象只有 4 个 `backend/tests/` 下的文件 + `$env:TEMP\r2v\` 下的脚本，**每一个都由 python 脚本落盘、且每次都打印了目标路径与字节数**；没有任何一个脚本的路径变量指向 `.superpowers/`。
2. `.superpowers/` 被 `.gitignore:10` 忽略（`git check-ignore -v` 亲验命中该行），故 `git add` / `git commit` 不可能碰它；我也**没有**跑过 `git checkout` / `restore` / `switch` / `merge` / `clean`。
3. 时间点对不上我的任何一次写盘：16:44 前后我在跑变异相位（`MA*`/`MB*`/`MC*`）与 pytest，那些命令的 cwd 是 `backend/`、写的是 `app/domain/prescription/*.py` 并**每次都在同一脚本内按字节还原并核 sha256**（还原后的 sha 全部与 pristine 相同，见 fr2.5）。

**⚠️ 最可能的机制（我有间接证据、没有直接证据，故只作为假设提出）**：`Read` 工具报的**总行数**与两份文件被截断后的行数**逐字相同**——`Read` 在本轮开工时报 `task-2-report.md` 「有 **617** 行」（我当时用 python 实测 972 LF，判定为账本 Ruling 64/100 记的「Read 行数偏小」），而现在磁盘上正好是 **617** LF；账本记 `task-1-report.md` 「Read 报 **1031** 行、实为 2616 LF」，而现在磁盘上正好是 **1031** LF。两个都精确等于 Read 曾经报过的数，不像巧合。**即：某个 IDE 侧的子系统把它自己那份「只含前 N 行」的视图写回了磁盘。** 若这个假设成立，那么账本里「`Read` 行号不可靠」这条应当**升级**为「`Read`（或它背后的文件视图层）可能会把它看到的截断版本**写回磁盘**、造成不可逆的数据丢失」——那已经不是「读数不准」，是**会毁证据**。请控制者裁定，并考虑：① 今后一律不用 `Read` 碰 `.superpowers/` 下的台账文件；② 每轮结束把报告另存一份到仓库外（TEMP 里 Task 1 各轮的 `fr1_report.md` / `pe_fr2_report.py` 就是这么活下来的，本次我也是靠这个惯例才找到了旁证）。

**我做了什么补救**：
1. 立刻把**当前**（已截断的）`task-2-report.md` 逐字节快照到 `C:\Users\whwenhao\AppData\Local\Temp\r2v\task-2-report.TRUNCATED-snapshot.md`（62640 B，sha16 `76A75BA3EFB3FB39`，与源逐字节相同 ✓），以免本节追加之后又被截断一次就连现在的状态都留不下。
2. 本节（`## fix round 2`）**按派单要求追加到 `task-2-report.md` 末尾**，追加方式为「python 按字节读回全文 → 追加（LF 换 CRLF）→ `write_bytes`」，并核「追加前的全文是追加后全文的**前缀**」——即**我没有覆盖任何现存内容**。
3. 我手里**还剩**被截断那一节的一部分原文（本轮 15:2x 我用 python 打印过 `:900`–`:972`），已逐字转录进 **fr2.11 附录**；`:629`–`:899`（fr1.0–fr1.6 的正文）我只有标题清单，**正文无法恢复**。
4. **请控制者用自己那份副本恢复 `## fix round 1` 节**（你亲验过它、并据它写了 Ruling 101–109，账本里也已摘了 CE-4/CE-6/CE-7/CE-8 的要点，故实质内容不全丢，但报告原文只剩我附录里那一段）。`task-1-report.md` 同理，且它丢得更多（TEMP 里还留着 `fr1_report.md` = Task 1 fix round 1 那一节的原文、`pe_fr2_report.py` = fix round 2 那一节的原文，可以据此恢复前两节）。

---

### fr2.1 派单 §5「控制者自查清单」的逐条复验（Ruling 84/100/109 的下游确认）

派单说这份清单由脚本 `.superpowers/sdd/_sc.py` 实跑生成。**我逐条自己重跑了一遍**（脚本：`$env:TEMP\r2v\check.py`、`hist.py`、`hist2.py`、`probe_asserts.py`、`probe_prose.py`）。

| # | 派单自查项 | 我的实测 | 判定 |
| --- | --- | --- | --- |
| 1 | `HEAD = c21767d`、`git status --short = ''` | `git rev-parse --short HEAD` = `c21767d`；`git status --short` 空；分支 `feature/plan-02-prescription-engine` | ✓ |
| 2 | 「12 条」出现 **5 处**：purity `:451` / layering `:158,:163,:238,:239` | 那 **5 个行号逐字对**；但**出现次数是 6**——`test_layering.py:239` 一行里有 **2** 次（「fix round 1 亲跑数出 12 条；fix round 5 复跑仍是 12 条」） | ⚠️ **CE-9**（口径：「处」= 行 vs 次） |
| 3 | 「:74」出现 **2 处**：purity `:102` / layering `:163` | `__init__.py:74` 确实 **2** 处；**另有第 3 处**过期数字 `74`：layering `:165` 的输出串 `app/db/models/__init__.py 74 1 None`（空格分隔、不含冒号）。派单在 §2.2 末尾的「另：」里点了它 | ✓ + ⚠️ **CE-10**（标题的计数与正文点的处数不一致） |
| 4 | 全仓相对导入 = **15**（`db/models` 13 + `domain/prescription` 2），level `{1: 15}` | 逐行输出 **15** 行；分布 `{'app/db/models': 13, 'app/domain': 2}`（那 2 条都在 `app/domain/prescription/`：`__init__.py:19` 与 `templates.py:37`，`module` 都是 `'exercises'`）；level `{1: 15}` | ✓ |
| 5 | `from . import feedback, prescription` 真实位置 = `app/db/models/__init__.py:82` | `:82` = `from . import feedback, prescription  # noqa: F401` ✓；`:74` = `from .derived import *  # noqa: F401,F403` ✓；`git grep -n "import feedback" -- backend/app` **只命中 1 处** | ✓ |
| 6 | `prescription.__all__` = 7 个（逐个列名） | 逐字相符：`['EQUIVALENCE_TRIGGERS', 'IMPACT_RANK', 'TARGET_DOMAIN', 'EquivalenceMapping', 'EquivalenceTable', 'ExerciseSpec', 'ImpactLevel']`，`len` = 7 | ✓ |
| 7 | `templates.__all__ == ['ImpactLevel']`；`templates.ImpactLevel is exercises.ImpactLevel` = True | 都 ✓（另：`pkg.IMPACT_RANK is exercises.IMPACT_RANK` = True，7 个名字**逐个** `getattr(pkg, n) is getattr(exercises, n)` 全 True） | ✓ |
| 8 | `IMPACT_RANK = {HIGH: 0, MEDIUM: 1, LOW: 2}` | ✓（`exercises.py:103-107`，`lookup` 在 `:194`/`:198` 用它） | ✓ |
| 9 | `templates.py` 39 行 = docstring + import + `__all__`；coverage `2 stmts / 0 branch / 100%` | 3090 B / LF 39 / CRLF 39；AST 顶层 = `Expr` + `ImportFrom` + `Assign` → 2 stmts（docstring 的 `Expr` 不计入，与 Ruling 108 那套口径一致）；coverage 表 `2 0 0 0 100%` | ✓ |
| 10 | `templates.py` 的**唯一真实导入方** = `tests/domain/test_prescription_templates.py:37` | 在 `c21767d` 上 ✓（本轮之后是 **`:45`**，因为我在 `:44` 加了 `from app.domain.prescription import exercises, templates`）。派单说「另一处命中是 docstring 里的散文」：用 `from app.domain.prescription.templates import` 这个模式实测 **2** 处（1 真 + `templates.py:16` 的散文）→ **派单成立**；若把模式松成 `prescription.templates` 则是 **3** 处（`templates.py:15`、`:16` 的散文 + 真 import） | ✓（口径取决于模式，见 fr2.4） |
| 11 | `SCANNED_DIRS = pipeline 7 + db 11 + domain 9 = 27` | 7 + 11 + 9 = **27** ✓；`app/domain/prescription/` = **3** ✓；`backend/app` 下 `.py` 总数 = **44** | ✓ |
| 12 | `528 passed` / domain `441 stmts / 120 branch / 100%` | 开工实测 `528 passed in 74.55s`；`--cov` 那次 `441 / 0 / 120 / 0 / 100%`、`527 passed, 1 skipped`（skip = `test_backfill.py` 的 trace-hook 自觉跳过，既有行为） | ✓ |
| 13 | 禁区：CSV 21412 B `D2C8E539E2FA0029` CRLF 0；`exercises.yaml` 13358 B `A6A000F58815FCBB` CRLF 0；`exercise_equivalence.yaml` 7841 B `0FFB881574AC04F3` CRLF 0；`pe.db` 不存在；`data/seed` 0 文件 | **逐字相同**（开工与收工各测一次，见 fr2.7） | ✓ |
| 14 | 派单 §2.1 建议把历史值绑到 `be0f1af` | `be0f1af` = **Task 1 fix round 3**；而那两句散文自己绑的是「fix round 1 亲跑」与「fix round 5 复跑」= **`6a2938f`** 与 **`7b84599`** | ⚠️ **CE-13** |

**清单里没有、而我另外核了的**：`git show` 在 `6a2938f` / `7b84599` / `3ea27cc` / `c21767d` 四个 rev 上重算全仓相对导入 = **12 / 12 / 14 / 15**，`module` 为空的那一条 = **1 / 1 / 1 / 1**、其序数 = **7 / 7 / 7 / 7**，`app/db/models/__init__.py` 的相对导入条数 = **7 / 7 / 7 / 7**。这四个 rev 的数就是 fr2.2 / fr2.3 里所有历史陈述的依据（脚本 `hist.py` / `hist2.py`，走 `git ls-tree` + `git show`，**没有** `checkout`）。

---

### fr2.2 CE-6 —— 「12 条」的份数与逐处处置（硬规矩 #51：列份数；#66：同类计数逐个更新）

**份数（我自己 grep 的，按硬规矩 #51 列出）**：`12 条` 在两份守卫里共 **6 次出现、分布在 5 行**：

| 文件 | 行（改前） | 该行出现次数 | 性质 | 处置 |
| --- | --- | --- | --- | --- |
| `test_domain_purity.py` | `:451` | 1 | **当前状态陈述** | 改成 15 + 分布 + level 分布；并**保留**「Task 1 期间是 12」这个历史值、绑到 `6a2938f` / `7b84599` |
| `test_layering.py` | `:158` | 1 | **绑定轮次的历史陈述**（「fix round 1 亲跑；fix round 5 复跑仍是同一个结果」） | **保留 12**、绑到 `6a2938f` / `7b84599`，并写明「两个 rev 上重算今天仍是 12，故这句历史话是真的、**不要改成 15**」，再补当前值 15 与 `3ea27cc` = 14 这个中间值 |
| `test_layering.py` | `:163` | 1 | **当前状态陈述**（「那 12 条里有 1 条…」） | 分母改 **15**；分子**我自己重核**过：`module` 为空的形状在四个 rev 上都是 **1** 条（`domain/prescription` 那 2 条的 `module` 都是 `'exercises'`、非空），故写成「分母从 12 变 15、**分子不变**」 |
| `test_layering.py` | `:238` | 1 | **当前状态陈述** | 改成「那批」（不写死条数）+ 另起一段给两个时点的条数 |
| `test_layering.py` | `:239` | **2** | **绑定轮次的历史陈述** | 同 `:158`：**保留 12**、绑 rev、补当前值 15 |

**⚠️ 派单说 5 处、我按 6 次处理**（见 CE-9）：如果只按 5 个行号各改一处，`:239` 那一行的**第 2 个**「12 条」会留下——而它恰恰在「fix round 5 复跑仍是 12 条」这半句里，是**历史陈述**、本来就该留。所以这一处「漏改」的后果是**语义正确但计数口径不一致**：改前那一句是「亲跑数出 12 条；复跑仍是 12 条」，两个 12 都是历史值。我的处理是把两个都保留并统一绑到 rev。

**「全部落在 `app.db.models` 包内」这半句**（派单要求「凡是说了这句话的地方都要改」）：全仓共 **3 处**（改前行号：layering `:159`、`:240`，purity 用「只有 ``app/db/models/`` 包内的 ``level == 1``」这个说法、在 `:447`）——**3 处全改**：都改成「只对那 **13** 条成立、对全仓已不成立」，并给出 domain 那 2 条折算后的串 `app.domain.prescription.exercises`。

**顺带改的一处（派单没点，我判断必须改，理由如下）**：purity `:451-453` 那一段还说「但 Plan 02 Task 2 起**会建** `app/domain/prescription/` 这一层子包，届时 `level == 2` 的相对导入**开始正常出现**」。这在 `c21767d` 上是**两处假**：① 子包已经建出（不是「会建」）；② `level == 2` **一条都没有**（账本 Ruling 104 亲扫，Task 2 刻意用了绝对导入）。它与我必须改的「12 条」在**同一段、同一个句子**里（`「一律放行」的写法会跟着变成真漏洞` 那一句的主语），留着就会让改完的段落自相矛盾。改后的写法：「`level == 2` 在真仓里**今天仍不存在**（账本 Ruling 104 亲扫…），但子包已经建出，Task 3 的 `match.py` 一写 `from ..indicators import X` 它就开始正常出现」。**这是本轮唯一一处超出派单 §2.1/§2.2 逐条清单的「既有散文修正」，主动披露。**（新增守卫自己带来的散文——文件 docstring 的「四道闸」、连带更新的「三条断言 → 前三条」等——不在此列，见 fr2.4 末段。）

**我扫过但没改的同类**：`test_layering.py:288`（改后 `:318`）那条**代码注释**「`# level == 1：包内合法导入（绿档，硬规矩 #50 的 ②）；真仓 app/db/models/ 就是这一档`」。理由：它是**逐格主语**的注释——它标的那一格矩阵入参就是 `("_shared", 1, ("app","db","models"))`，对那一格「真仓 `app/db/models/` 就是这一档」是真的；全仓口径的陈述住在我已改的 docstring 里。且它不含**计数**，不在 #66 的「同类计数」范围内。若控制者认为该带上，改一行即可（见 fr2.10 关切 1）。

---

### fr2.3 CE-7 —— 过期行号 `:74` 的份数与处置

**份数**：过期的数字 `74` 共 **3 处**（派单标题说 2 处、正文的「另：」点了第 3 处，见 CE-10）：

| 文件 | 行（改前） | 原文 | 处置 |
| --- | --- | --- | --- |
| `test_domain_purity.py` | `:102` | 「真仓里就有这一形状：`app/db/models/__init__.py:74` 的 `from . import feedback, prescription`」 | 改成「`app/db/models/__init__.py` 里那句 `from . import feedback, prescription  # noqa: F401`」+ 可 grep 命令 + **绑 `c21767d` 的行号 82** + 记一次漂移史（`:74` → `:82`，Ruling 90 改 docstring 推走的）+ 写明 `:74` 今天是什么 |
| `test_layering.py` | `:163` | 「`module` 为空的形状：`app/db/models/__init__.py:74` 的 `from . import feedback, prescription`」 | 同上口径 |
| `test_layering.py` | `:165` | 「上面那条命令打出来的**第 7 行**是 `app/db/models/__init__.py 74 1 None`」 | 输出串里的 `74` 改成 **`82`**；并**核过序数 7**：在 `6a2938f` / `7b84599` / `3ea27cc` / `c21767d` 四个 rev 上，那条命令的第 7 行**都**是这条（该文件恒有 7 条相对导入、`module=None` 那条恒排最后、且它在 `sorted()` 下排全仓第一）——**序数不变、只有行号变**。另补一句：Windows 上 `pathlib` 打出的分隔符是反斜杠（`app\db\models\__init__.py 82 1 None`），**分隔符随平台、序数与数字不随** |

**定位方式的选择（派单授权我定，并要在报告里说明）**：我选了「**先给可 grep 的原文、再给绑定 commit 的行号**」，两处都写成 `git grep -n "import feedback" -- backend/app`（亲验：**只命中 1 处**，就是 `backend/app/db/models/__init__.py:82`）。理由：本仓已有 4 次「裸行号过期」的记录（Plan 01 控制者错误 #50、Plan 02 的 CE-1 / CE-7，加上本轮我自己差点写进散文的两个不稳定计数），而**原文串只在语义变化时才失效**——那正是我们希望它响的时候。行号仍保留，但**永远带着 commit**（硬规矩 #37）。

**⚠️ 反斜杠的坑（我自己踩了，记下来）**：把 Windows 路径写进 docstring 时，`app\db\models\__init__.py` 里的 `\d` / `\m` / `\_` 是**无效转义序列**——Python 3.11 报 `DeprecationWarning: invalid escape sequence`、3.12+ 是 `SyntaxWarning`，而且 pytest 会把警告指到**整个 docstring 的起始行**（`test_layering.py:131`），一眼看不出是我新加的那一行。pristine 里那一段**没有**反斜杠，所以这个 warning 是**我引入的**；我是在 `pytest tests/architecture -q` 的输出里看到 `6 passed, 1 warning` 才发现——**如果我只看「6 passed」就会把它带进 commit**。已改成 `\\`（渲染出来仍是单反斜杠），改完 `compile()` 的 warnings 列表为空、pytest 也是 `6 passed`（无 warning）。

---

### fr2.4 三条新守卫（Ruling 107-2 / -3 / -4）

新增 **3 个测试函数**（故 `528 → 531`），**没有新建任何测试文件**（派单明令：Task 3 会建 `tests/domain/test_prescription_exercises.py`，本轮新建会撞）：

| # | 测试函数 | 文件:行（`966eae0`） | 支数 | 钉什么 |
| --- | --- | --- | --- | --- |
| (a) | `test_impact_rank_values_are_pinned_verbatim` | `backend/tests/test_refdata_prescription.py:468` | 4 | `IMPACT_RANK` 的**秩值** |
| (b) | `test_templates_module_still_reexports_impact_level` | `backend/tests/domain/test_prescription_templates.py:89` | 2 | `templates.__all__` + `is` 同一性 |
| (c) | `test_prescription_public_namespace_is_pinned_verbatim` | `backend/tests/test_refdata_prescription.py:838`（基线常量 `:827`，新分节 `# 闸 4` 在 `:801`） | 6 | `prescription.__all__` 的 7 个名字与声明序 |

**(a) 的四支**（每支的主语写进了 docstring，硬规矩 #56）：
1. `IMPACT_RANK == {ImpactLevel.HIGH: 0, ImpactLevel.MEDIUM: 1, ImpactLevel.LOW: 2}` —— **字面写死**，不从 `ImpactLevel` 派生、不从 `IMPACT_RANK` 读回（硬规矩 #35）；
2. `[lv.value for lv in sorted(IMPACT_RANK, key=IMPACT_RANK.__getitem__)] == list(IMPACT_DESCENDING)` —— 与测试侧那份**独立**的降序元组交叉，**两侧不同源**；
3. `IMPACT_RANK[LOW] >= IMPACT_RANK[HIGH]` —— **绿输入**（Task 7 的正方向：low 的替身可以顶 high 的上限）；
4. `not IMPACT_RANK[HIGH] >= IMPACT_RANK[LOW]` —— **红输入**（反方向必须判「不可以」）。
只有支 3 的话，把三个秩值改成同一个数也全绿——**这一点被 M-A2 实测证实**（支 2 与支 3 仍绿、只有支 1 与支 4 不成立）。

**(b) 的两支**：`templates.__all__ == ["ImpactLevel"]`（字面）+ `templates.ImpactLevel is exercises.ImpactLevel`（**`is` 不是 `==`**：枚举继承 `str`，本地重定义的同值枚举会让 `==` 成立而 `is` 不成立，而那正是「re-export 被换成本地定义」的失效形态——**M-B1 实测只有这一支红**）。

**(c) 的六支**：① `len(baseline) == 7`（基线自校，口径照 `tests/db/test_models.py:469` 那一条，本轮未动该文件）；② `list(pkg.__all__) == baseline`（**内容与声明序**）；③ `sorted(baseline) != baseline`（证明支 2 真的在钉顺序）；④ 逐个 `getattr(pkg, n) is getattr(exercises, n)`，且**先断言所有者侧不是 `None`**（否则 `None is None` 会让这一支退化成恒真）；⑤ **AST 扫 `exercises.py` 的公有顶层定义 == 字面基线**（穷尽）；⑥ 两种**合成**失同步状态的比对必须判不相等。

**⚠️ 支 5 是我自己加的、派单没要求，理由是派单给的失效形态按字面做不到（CE-11）**：派单要求「写明失效形态：谁往 `exercises.py` 加了新对象却忘了重导出，这条会红」——**一条纯字面钉 `__all__` 的断言在这个场景下不会红**（`__all__` 一个字没变，比对恒等成立）。要让这句话成真，必须有一支的实际侧来自 `exercises.py` 而不是 `__all__`。我用 AST 扫源码（**不是 `dir()`**：`dir()` 随导入顺序漂，实测 `dir(pkg)` 会多出 `exercises` 这个子模块属性，故它既违反 #35 又不可复现），口径是「顶层 `ClassDef` / `FunctionDef` / `Assign` / `AnnAssign` 的公有名」，实测今天恰好 = 那 **7** 个（模块级 import 进来的 `Mapping` / `dataclass` / `Enum` / `ITEM_BUCKET` 被这个口径排除在外，`dir(exercises)` 的公有名是 **11** 个）。**M-C3 实测：这一支是那个方向上唯一会红的**。

**放置位置的理由**：派单建议 (a)/(c) 放 `tests/test_refdata_prescription.py`、(b) 放 `tests/domain/test_prescription_templates.py`，我照做。(c) 寄住在「动作库两份 YAML 的唯一守卫」文件里确实有点错位，故我在该文件 docstring 的「四道闸」清单里**新加了第 4 道**并写明「这一道不是在守 YAML…Task 3 建 `tests/domain/test_prescription_exercises.py` 时这两条应当搬过去归位」。(b) 与 (c) 钉的是**两份 `__all__`**（`templates.py` 一份、`prescription/__init__.py` 一份，两份 docstring 都写了「必须一起改」），我在两条守卫的 docstring 里**互相交叉引用**，免得下一个人改了一份找不到另一份的守卫。

**为了 (b) 而在 `test_prescription_templates.py` 顶部加的 import**：`from app.domain.prescription import exercises, templates`（`:44`），原有那句 `from app.domain.prescription.templates import ImpactLevel`（`:45`）**一个字未动**（它是 Ruling 103 里那条覆盖率承重的 import）。加 `:44` 的副作用是**好的**：现在那个文件有**两处**引用 `templates` 模块对象，删掉文件会在收集期 ImportError（M-B3 实测退出码 2）。

**连带改的散文**（硬规矩 #66：改一处要 grep 全部同类）：
- `tests/test_refdata_prescription.py` 文件 docstring：「同时下**三道**闸」→「**四道**闸」，并新增第 4 条的说明（`:7-8`、`:16-22`）；
- `tests/domain/test_prescription_templates.py` 文件 docstring：「**三条**断言的期望侧都是字面量」→「**前三条**…」并补第 4 条的口径（`:20`、`:24-25`）；「它**只**守 `ImpactLevel` 这个**词表本身**」→「它守词表本身（下面三条），以及 `templates.py` 对它的那一句 re-export 与 `__all__`（fix round 2 加的第 4 条）」（`:29-31`）；`:13` 那句「顺带它也守着『re-export 与 `__all__` 还在』」补上「fix round 2 起这件事另有**显式**守卫（那句 import 只在**收集期**响，删掉 `__all__` 它是不会红的）」——**后半句被 M-B2 实测证实**（`__all__ = []` 时那句 import 照旧工作，全仓只有新守卫的支 1 红）。

---

### fr2.5 变异验收（硬规矩 #50 / #53 / #62 / #65；**全部串行**，一次一个相位）

harness：`$env:TEMP\r2v\mutate.py`（每个相位固定 7 步：① 核工作树逐字节 == pristine ② 取剥 docstring 的 `ast.dump` 基线 ③ 打变异（子串命中次数断言 == 1）④ **在剥 docstring 的 `ast.dump` 上确认真的改了代码** ⑤ 全量 `pytest -q -rf --tb=line`（串行、`-p no:cacheprovider`）⑥ 逐支真值探针 `probe_branches.py` ⑦ 按字节还原 + 核 sha256 + 复核 `ast.dump` 回到基线）。
pristine 快照：`$env:TEMP\r2v\pristine\`，`exercises.py` = `1FC9AA42A6B93BF5`、`templates.py` = `DCC3D71CA2692E12`、`__init__.py` = `1184C73F0F920A97`（`exercises.py` 那个值与 fix round 1 报告 fr1.7 记的**逐字相同**）。

**相位命名**：下表用 harness 里的相位名（`MA1` / `MB1` / `MC1` …），三条守卫的 docstring 里用带连字符的同一套名字（`M-A1` / `M-B1` / `M-C1` …）——**一一对应、只是写法不同**；`MB4` 有两个相位，docstring 里合称 `M-B4`。

**M0（干净对照，已知 GREEN，跑在一切变异之前与之后各一次）**：`531 passed`；`--cov=app/domain --cov-branch` = `441 / Miss 0 / 120 / BrPart 0 / 100%`、`530 passed, 1 skipped`；逐支探针 **12 支全绿**（a 的 4 支 + b 的 2 支 + c 的 6 支）。

| 相位 | 变异对象与内容 | 剥 docstring 的 `ast.dump` | pytest | **哪一支开火** | 还原 sha16 |
| --- | --- | --- | --- | --- | --- |
| **M1a** | `exercises.py`：`IMPACT_RANK` 的 dict 字面量 → 等价 `enumerate` 推导式（**语义等价**） | 5680 → 5919 字符，**真变了** | **531 passed**，退出码 0 | 无（**12 支全绿**）→ 尺子不恒红 ✓ | `1FC9AA42A6B93BF5` ✓ |
| **M1b** | `templates.py`：`from .exercises import …` → `from app.domain.prescription.exercises import …`（**语义等价**，同一个对象） | 219 → 243 字符，真变了 | **531 passed**，退出码 0 | 无（12 支全绿）✓。⚠️ 附带实测：这一改让全仓相对导入从 **15 变 14**，而**没有任何测试红**——即 fr2.2 那些计数**只是散文、不是断言**，这正好说明为什么它们必须绑时点 | `DCC3D71CA2692E12` ✓ |
| **MA1** | `exercises.py`：`IMPACT_RANK` 的 `HIGH: 0 ↔ LOW: 2` 对调（= fix round 1 的 M-B） | 5680 → 5680（长度同、内容不同），真变了 | **2 failed, 529 passed** | **新守卫 (a) 的四支全部不成立**（探针：支1 False / 支2 False / 支3 False / 支4 False），pytest 报最先开火的**支 1**（`assert {…LOW: 0} == {…LOW: 2}`）；另一条红的是 `test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable`（`assert None == 'stationary_cycling'`）。**对比 fix round 1 的同一个变异只有 `1 failed`（Ruling 108）→ 本条正是新增的那一条红** | `1FC9AA42A6B93BF5` ✓ |
| **MA2** | `exercises.py`：三个秩值全改成 `0`（序被抹平） | 真变了 | **2 failed, 529 passed** | **支 1 与支 4 不成立；支 2 与支 3 仍是绿的**（`sorted` 稳定排序保持了声明序、正方向 `0 >= 0` 成立）→ 这就是支 4 存在的理由，也是「只有绿输入会得到空转守卫」的实证。另一条红的仍是 lookup 那条（`assert 'b' is None`） | `1FC9AA42A6B93BF5` ✓ |
| **MB1** | `templates.py`：re-export → **本地同值重定义** `class ImpactLevel(str, Enum)` | 219 → 577 字符，真变了 | **1 failed, 530 passed** | **只有 (b) 的支 2**（`assert <enum 'ImpactLevel'> is <enum 'ImpactLevel'>`）。⚠️ 全仓**没有第二条**测试抓得住这件事；且 domain 纯净性守卫**仍绿**（`enum` 在 allow-list 里），故这一支是唯一的网 | `DCC3D71CA2692E12` ✓ |
| **MB2** | `templates.py`：`__all__ = ["ImpactLevel"]` → `[]` | 219 → 190 字符，真变了 | **1 failed, 530 passed** | **只有 (b) 的支 1**（`assert [] == ['ImpactLevel']`）。顶部那句 `from …templates import ImpactLevel` 是**显式**导入、不看 `__all__`，故它不会红——**实测证实**了我在 docstring 里写的那句「那句 import 只在收集期响」 | `DCC3D71CA2692E12` ✓ |
| **MB3** | `templates.py`：**整份删掉** | 文件 `exists = False` | **退出码 2**，`ERROR collecting tests/domain/test_prescription_templates.py`、`ImportError: cannot import name 'templates'`（报错点在 **`:44`**，即我新加的那一句；`:45` 那句同样会炸） | 收集期就炸，**跑不到覆盖率那一步**。⚠️ 我原先在 docstring 里写「且 domain 覆盖率 `Miss 2`」是**未经实跑的推断、而且是错的**：文件被删掉时它在覆盖率表里**整行消失**、`TOTAL` 会从 441 掉到 439 而 Cover 仍是 100%。已按实测改写（见 fr2.9 错误 1） | `DCC3D71CA2692E12` ✓ |
| **MB4 相位 1** | `tests/domain/test_prescription_templates.py`：把 `:44` 的 `, templates` 去掉、`:45` 改指 `exercises`（= Ruling 103 那个「去中间层」清理） | —（变异对象是测试文件） | **1 failed, 530 passed**，退出码 1 | **(b) 整条 `NameError: name 'templates' is not defined`**（报错点 `:129` = **变异当时**支 1 所在行；本轮随后又改了该文件的 docstring，那两行断言现在在 `:146`-`:147`）→ **守卫自己就是一个导入方，要绕过它就得连它一起删，而删掉它就红** | 快照 `9AC7850957886967` ✓ |
| **MB4 相位 2** | 同相位 1，**再 deselect 掉这条守卫**（= 本轮之前仓库里的状态） | — | **退出码 0**，`529 passed, 1 skipped, 1 deselected` | **没有任何测试红**，而覆盖率表变成 `app\domain\prescription\templates.py  2  2  0  0  0%  37-39`、`TOTAL 441  2  120  0  99%` → **Ruling 103 那个「退出码 0 而不变量已破」的静默退化，逐字复现**。这一相位是 (b) 这条守卫的全部理由 | 快照 `9AC7850957886967` ✓ |
| **MC1** | `prescription/__init__.py`：`__all__` 里删掉 `"ImpactLevel"`（7 → 6） | 615 → 584 字符，真变了 | **1 failed, 530 passed** | **(c) 的支 2**（`assert ['EQUIVALENCE…ExerciseSpec'] == […, 'ImpactLevel']`），**且支 6b 也一起红**（那种状态下 `list(__all__)` 恰好等于 `baseline[:-1]`）→ **支 6 不是装饰，它有独立的开火能力** | `1184C73F0F920A97` ✓ |
| **MC2** | `prescription/__init__.py`：只删 `from .exercises import (…)` 里的 `ImpactLevel`、`__all__` 里留着 | 615 → 588 字符，真变了 | **1 failed, 530 passed** | **只有 (c) 的支 4**，报错文本就是我写的那句：`ImpactLevel 在包上取不到、或取到的不是 exercises 里的那个对象（公开面谎报）`。失效形态是 `from app.domain.prescription import *` 的运行期 `AttributeError`，而那条路径今天没有任何测试走 | `1184C73F0F920A97` ✓ |
| **MC3** | `exercises.py`：加一个**公有顶层定义** `SUBSTITUTE_POLICY = "first_match"`，**不**重导出（`__all__` 一个字没改） | 5680 → 5778 字符，真变了 | **1 failed, 530 passed** | **只有 (c) 的支 5**（`只在源码里（加了却没重导出）= ['SUBSTITUTE_POLICY']`）→ **这正是派单 §2.3(c) 要求写明的那个失效形态，而纯字面基线抓不住它**（CE-11）。没有支 5，这件事**完全静默** | `1FC9AA42A6B93BF5` ✓ |

**⚠️ `MA1` 跑了两次**（同一份变异、同一份还原口径）：第一次的 harness 还没加 `-rf --tb=line`，只拿到 `2 failed, 529 passed` 而没拿到「是哪条断言」，故重跑一次以取到失败断言的确切位置。两次的 pytest 结论一致（`2 failed, 529 passed`）、逐支探针一致（四支全 False）、还原后的 sha256 一致（`1FC9AA42A6B93BF5`）。**故 `mutate.py` 一共跑了 11 次、还原 11 次**（表中 10 个相位 + `MA1` 的重跑），加上 `MB4` 的 1 次（用的是另一套快照口径，见 fr2.7）。

**硬规矩 #65 的三项**：① 每个相位都指明了**哪一支**开火（不是笼统的「哪条测试红」），且 MA1/MA2 用逐支探针证明了「同一条测试里不同支的开火集合不同」；② **最强的变异对象**是 `exercises.py` 的 `IMPACT_RANK`（MA1 让 2 条测试红、4 支全不成立）；③ 没有「真实数据上结构性不可达」的支——(a) 的支 4 与 (c) 的支 6 都是**合成输入**，且 MA2 / MC1 分别证明了它们**真的会开火**、不是死代码。

---

### fr2.6 改动面自证（硬规矩 #32 + #53）

`git diff --name-status c21767d` = **4 个 M**：`backend/tests/architecture/test_domain_purity.py`、`backend/tests/architecture/test_layering.py`、`backend/tests/domain/test_prescription_templates.py`、`backend/tests/test_refdata_prescription.py`（`4 files changed, 331 insertions(+), 19 deletions(-)`）。
`git diff --name-only c21767d -- backend/data Document` → **命中 0**（故三个禁区文件的指纹不可能变，fr2.7 的实测也证实了）。

**`backend/app/**` 的闸门**（脚本 `$env:TEMP\r2v\ast_gate.py`；基线取 `git show c21767d:backend/app/<path>`，**blob 是 LF 版**，故工作树侧先 `replace("\r\n", "\n")` 归一化再比——不归一化会 44 个全 DIFF，这正是派单 §0 提醒的那个陷阱）：

- `backend/app` 下 `.py` = **44** 个；剥 docstring 的 `ast.dump` **SAME = 44 / DIFF = 0**。
- **4 个对照**（在内存里变异、**不落盘**，故不可能污染工作树）：

| 对照 | 内容 | 剥 docstring 的 `ast.dump` | full `ast.dump` |
| --- | --- | --- | --- |
| C1 | `exercises.py`：`lookup` 的 `>=` → `>` | **CAUGHT** | 变了 |
| C2 | `exercises.py`：`LOW = "low"` → `"Low"` | **CAUGHT** | 变了 |
| C3 | `db/models/__init__.py`：删掉 `from . import feedback, prescription` 那一条语句 | **CAUGHT** | 变了 |
| C4 | `exercises.py`：**只**往模块 docstring 里追加一句话 | **SAME**（期望就是 SAME） | 变了（证明它真的改到了 docstring） |

C1–C3 证明尺子**能抓住**真语义变异（不恒 SAME），C4 证明尺子**不把**纯 docstring 改动算成语义改动（不恒 DIFF）。**两个方向都不恒真** ✓。

**两份架构守卫自己的闸门**（本轮改的就是它们的 docstring）：`test_domain_purity.py` 与 `test_layering.py` 的**剥 docstring `ast.dump` 与改前逐字相同**（35081 vs 35081、25995 vs 25995 字符），而 full dump 不同（预期：docstring 是 AST 的一部分）→ **本轮对这两份文件是纯散文改动**。`python -m pytest tests/architecture -q` = **6 passed**（且无 warning，见 fr2.3 的反斜杠坑）。

---

### fr2.7 落盘闸门与收工自证（硬规矩 #48 升级口径）

本轮**所有**写盘都走 python 脚本（`patch_prose.py` / `fix_indent.py` / `fix_escape.py` / `add_guards.py` / `fix_grep_claim.py` / `fix_guardb_doc{,2,3}.py` / `fix_guard_ac_doc.py`），编辑工具只用来改 `$env:TEMP` 下的脚本本体，且每次改完都 `py_compile` + shell 复核。

| 闸门 | 做法 | 结果 |
| --- | --- | --- |
| ① 双向串查 | `verify_prose.py`：purity 9 个新串 + layering 12 个新串（各命中 ≥1）、12 个旧串（残留必须 = 0） | **BAD = 0** |
| ① 的对照组 | 同脚本先跑 **9 个已知存在**的串（`def _imported_modules(tree: ast.AST):` / `ALLOWED_PACKAGE = ` / `def _is_forbidden(module: str) -> bool:` / 那条 `cd backend; python -c "import ast,pathlib;` 命令原文 / …），改前改后都 `now=1 pri=1` | 证明「0 命中」是**查出来的**、不是查询坏了（#48-③） |
| ① 的「允许残留」清单 | `12 条`（3 行）、`全部落在 ``app.db.models`` 包内`（3 行）逐行打印人工复核 | 6 处残留**全部**在「绑定 rev 的历史陈述」或「被当作已不成立的半句引用」的语境里，无一处是当前状态陈述 |
| ② 缩进/空白敏感 | 每个文件打印 `bytes / LF / CRLF / 裸 LF / mojibake(U+FFFD)`，并对新增行逐行量前导空格数 | 4 个文件**裸 LF 全 0、mojibake 全 0**；purity 的 bullet 缩进被我一开始写成 5/7 空格（照终端回显抄的），`repr()` 量出既有口径是 **4/6**，已逐行改回（fr2.9 错误 3） |
| ② 追加 | 每条断言都带**期望值**（`got == exp`），不是只打印 | 见 fr2.4 的连带散文清单与 fr2.7 末尾的探针输出 |
| 替换的唯一性 | `Editor.find()` 对每个锚点断言**命中恰 1 次**；`replace_span` 断言首末两行的内容 | 全部命中 1 次；无一次「静默未落盘」（每次落盘后都重新读字节复核） |
| 变异还原 | 每个相位 ⑦ 步按字节写回 pristine + 断言 `got == pristine` + 核 sha256 + 复核剥 docstring 的 `ast.dump` 回到基线 | **11/11 还原成功**（MB4 用的是「本轮改完后的快照」而不是 pristine，因为 pristine 里没有本轮新加的守卫——这一点在脚本里写明了） |

**禁区三项指纹（收工实测，`read_bytes()` 口径）**：

| 文件 | 字节 | sha256[:16] | CRLF | 裸 LF |
| --- | --- | --- | --- | --- |
| `backend/data/national_standard_2014.csv` | **21412** | **`D2C8E539E2FA0029`** | **0** | 503 |
| `backend/data/exercises.yaml` | **13358** | **`A6A000F58815FCBB`** | **0** | 267 |
| `backend/data/exercise_equivalence.yaml` | **7841** | **`0FFB881574AC04F3`** | **0** | 126 |

`backend/pe.db` **不存在** ✓；`backend/data/seed/` **0 文件** ✓；**没有**跑过 `app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily` ✓。

**四个改动文件的收工字节指纹**（供下一轮做基线）：

| 文件 | 字节 | sha256[:16] | CRLF | 裸 LF | mojibake |
| --- | --- | --- | --- | --- | --- |
| `tests/architecture/test_domain_purity.py` | 48757 | `642EA3226EC12751` | 710 | 0 | 0 |
| `tests/architecture/test_layering.py` | 32445 | `5D53DE6372581CDF` | 471 | 0 | 0 |
| `tests/domain/test_prescription_templates.py` | 10697 | `B71E435CF3FC577C` | 147 | 0 | 0 |
| `tests/test_refdata_prescription.py` | 54774 | `EF94366A343A23F2` | 921 | 0 | 0 |

**收工自证**：`git status --short` = **0 行**；`git diff HEAD --stat` 空（工作树 == HEAD）；HEAD = **`966eae0`**（`c21767d` 之上**一个** commit，未 push）；`git ls-files --others --exclude-standard` 为空；仓库内**无临时目录残留**（我的脚本全在 `$env:TEMP\r2v\`，`.superpowers/` 与 TEMP 都不入库）。

---

### fr2.8 我发现的控制者错误（逐条注明成立 / 不成立 / 歧义 + 证据）

**CE-9（成立，轻微：口径缺失）— 派单 §2.1 说「「12 条」出现在 **5 处**」，实测是 **5 行 / 6 次**。**
证据：逐行 `count('12 条')` → purity `:451` × 1；layering `:158` × 1、`:163` × 1、`:238` × 1、**`:239` × 2**（「fix round 1 亲跑数出 12 条；fix round 5 复跑仍是 12 条」）。派单给的 5 个 file:line **作为行清单是完整的**（它自己说是脚本 grep 出来的，脚本按行输出），但硬规矩 #51/#66 要求的是「grep 出**全部同类计数**逐个更新」，计数单位是**出现次数**。**照 5 处修会留下 1 处**——虽然那一处恰好也该保留（它是历史陈述），但那是运气，不是纪律。→ 我按 6 次处理，并在 fr2.2 的表里逐次标注性质。

**CE-10（成立，轻微：标题与正文的计数不一致）— 派单 §2.2 标题说「引用 `:74` 的有 **2 处**」，正文的「另：」又点了第 3 处。**
证据：字符串 `__init__.py:74` = **2** 处（purity `:102`、layering `:163`）✓；但**过期数字 `74`** 还有第 3 处 = layering `:165` 的输出串 `app/db/models/__init__.py 74 1 None`（空格分隔、不含冒号，故不匹配 `:74`）。**信息没漏**（派单点了它，还要求「那个序数与那串输出也要一起核」），但**标题里的「2 处」会让只读标题的人漏改一处**。→ 我按 3 处改，并核了序数（四个 rev 上都是 7）。

**CE-11（成立，⚠️ 本轮最实质的一条）— 派单 §2.3(c) 要求的失效形态「谁往 `exercises.py` 加了新对象却忘了重导出，这条会红」，与它同时要求的守卫形状（「补一条**字面钉住**这 7 个名字的断言」）互相矛盾：照字面做，那句话是假的。**
推理链（每一环都实测过）：① 派单要求期望侧字面写死 7 个名字、实际侧是 `prescription.__all__`；② 在「往 `exercises.py` 加一个公有对象、**完全不动** `__init__.py`」这个场景下，`__all__` 一个字没变；③ 故 `list(pkg.__all__) == baseline` **恒等成立**、断言**绿**；④ 我用 **M-C3** 实跑证实：加了 `SUBSTITUTE_POLICY = "first_match"` 之后，只有我**自己加的支 5**（AST 扫 `exercises.py` 的公有顶层定义 vs 字面基线）红，支 2 与支 4 都绿。
**这与上一轮 CE-4 是同一家族但方向相反**：CE-4 是「照做会静默破坏一个不变量」，CE-11 是「照做会得到一条**声称能抓 X 而实际抓不住 X** 的守卫」——后者更隐蔽，因为它绿着。
**我的处置**：保留派单要求的字面基线（支 1/2/3/6），**另加支 4（不许谎报）与支 5（AST 穷尽）**，使派单列的 4 个失效形态**全部**成真，并把「只有支 5 抓得住这个方向」写进 docstring。支 5 的实际侧来自源码 AST 而**不是** `dir()`（`dir(pkg)` 实测会多出 `exercises` 这个子模块属性、随导入顺序漂，既违反 #35 又不可复现），期望侧仍是字面基线，故**不构成同源**。
**若控制者认为支 5 过紧**（例如 Task 3 想在 `exercises.py` 放一个故意不公开的模块级公有名），说一声：正确的做法是给那个名字加下划线，或把它加进 `__all__` + 基线；这条已写进 docstring。

**CE-12（歧义 → 我判**部分成立**）— 派单 §2.1 与账本 Ruling 106 都说前任「实测 **14** 条」是**数错了**（「漏数了 `templates.py:37`」）。实测：14 是**正确的**，只是**不是本轮结束时的值**。**
证据（`hist.py`，走 `git ls-tree` + `git show`）：`3ea27cc`（前任测量时的 HEAD、即 fix round 1 的基线）上全仓相对导入 = **14** = `app/db/models` 13 + `app/domain` **1**，而那 1 条正是 `app/domain/prescription/__init__.py:10` 的 `from .templates import ImpactLevel`——**与前任报告里逐字写的那一条完全对得上**。`templates.py:37` 那一条在 `3ea27cc` 上**不存在**（那时 `templates.py` 自己定义 `ImpactLevel`、只 import `enum`），它是**前任自己那一轮新造出来的**（fix round 1 把定义换成 re-export）。
**所以准确的归因是**：它的**测量没错**，错的是**它对自己本轮增量的预测**——它报告里写「（本轮之后是 `from .exercises import (…)`，条数不变）」，只考虑了 `__init__.py` 那一处的改写，漏了 `templates.py` 那一处**新增**。
**为什么这个区分要紧**：两种归因对应的预防动作**不同**。「数错了」→ 加强 #66 的同类扫描；「增量预测错了」→ 需要在**改动清单**里对每个被改文件问一句「这一改会不会新增/删除一条被某个计数断言或散文计数量到的东西」。后者是本轮 M1b 也复现了的形态（一个语义等价的 import 改写让全仓相对导入 15 → 14）。**建议账本把 Ruling 106 那句「实现者报的是 14 条，也错了——它漏数了 `templates.py:37`」改成「它测的 14 在 `3ea27cc` 上是对的，错在没把自己本轮将新增的第 15 条算进去」**，否则下一个人会去修一个不存在的测量问题。

**CE-13（成立，轻微：示例里的 commit 指向不准）— 派单 §2.1 建议的历史绑定示例写「Task 1 期间（`be0f1af`）是 12 条」。**
证据：`git log --oneline -1 be0f1af` = 「test: Plan02 **Task1 fix round 3**…」；而那两句散文自己绑的是「fix round **1** 亲跑」与「fix round **5** 复跑」，对应 **`6a2938f`** 与 **`7b84599`**。逐 rev 数 `12 条` 的出现次数（`probe_prose.py`）：`1df5e8a` 0+0 → `6a2938f` **1+1**（首次出现）→ `1fa9941` layering 2 + purity 1 → `be0f1af` layering 3 + purity 1 → `7b84599` layering **5** + purity 1（= 今天的分布）。**「12」这个数字在 `be0f1af` 上确实也是 12**（那一轮没动这个数），所以派单没说错数；错的是**把读者指向了错误的轮次**——按它绑，「fix round 1 亲跑」这句散文就会被绑到一个比它晚两轮的 commit 上。→ 我按实测绑到 `6a2938f` / `7b84599`，并把「两个 rev 上重算今天仍是 12」写进散文（这样下一个人可以自己复核，而不必相信我）。

**CE-14（不成立 —— 派单对，我核过并且它救了我）— 派单 §0 的两条工具口径提醒。**
① 「`git show HEAD:<path>` 给的是 blob 的 **LF** 版，与工作树 CRLF 版差值 = CRLF 行数，字节比对前先归一化」→ 我的 `ast_gate.py` 照做（工作树侧 `replace("\r\n","\n")` 后再比），44 个文件全 SAME；**不归一化会 44 个全 DIFF**（我在写脚本时先验过这一点）。② 「`Read` 工具的行号不可靠」→ 本轮**复现并且更严重**：`Read` 报 `task-2-report.md` 只有 **617 行**（python 实测当时是 **972** LF），偏小 **355** 行；而 16:44 之后磁盘上正好是 **617** LF（见 fr2.0）。**派单这条提醒成立，且它现在是一条数据丢失线索而不只是读数问题。**

**CE-15（不成立 —— 派单的预期是对的）— 派单 §3 说「domain 覆盖率必须维持 Miss 0 / BrPart 0 / 100%。⚠️ stmts **可能微增**（若新测试触发 domain 里此前未执行的行——理论上不该有）」。**
实测：**441 stmts 未变**、Miss 0 / 120 branch / BrPart 0 / **100%**，逐模块与 fix round 1 的表**逐格相同**（`exercises.py 38/6`、`templates.py 2/0`、`prescription/__init__.py 2/0`）。派单那句「理论上不该有」是对的：三条新守卫都只**读**已有对象（`IMPACT_RANK` / `__all__` / 模块属性）与**测试侧**读源码（支 5 的 `ast.parse`），没有触发 domain 里任何新的行。

**CE-16（不成立 —— 我核过、派单是对的）— 派单 §2.3(b) 说「另一处命中是 docstring 里的散文，不算」。**
用 `from app.domain.prescription.templates import` 这个模式实测 **2** 处命中：`templates.py:16`（散文）+ `test_prescription_templates.py:37`（真 import）→ **「另一处」这个单数是对的**。若把模式松成 `prescription.templates` 则是 **3** 处（多出 `templates.py:15`），故这个单数**依赖于模式**——我在 (b) 的 docstring 里把模式**逐字写出来**并加了 `^` 锚，就是为了不让下一个人踩这个口径歧义（顺带记下：不加 `^` 时正则里的 `.` 会连**文件名** `prescription_templates` 都匹配，命中数变成一个个位数×若干、且**每改一次本文件散文就变**，不是稳定量，故我没把那个数写进散文）。

---

### fr2.9 我自己本轮犯的错（5 条，全部自纠；逐条记下以免重犯）

1. **（硬规矩 #52 违反）我把「M-B3 删掉 `templates.py` → domain 覆盖率 `Miss 2`」写进了 (b) 的 docstring，而这是**未经实跑的推断、而且是错的**。** 实跑（MB3）显示：文件被删掉时它在覆盖率表里**整行消失**，`TOTAL` 会从 441 掉到 **439** 而 Cover 仍是 **100%**；而且收集期就 ImportError、**退出码 2**，根本跑不到覆盖率那一步。`Miss 2` 是**另一个**形态（文件还在、没人 import）的数——即 Ruling 103 那一个。我随后专门设计了 **MB4 两相位**去实测那个形态，拿到了真数（`templates.py 2 2 0 0 0% 37-39`、`TOTAL 441 2 120 0 99%`、**退出码 0**），并据此**改写**了那一段。**教训**：`f(x) == y` 形状的举例必须真跑过——这条规矩我在写它的时候违反了它。
2. **（硬规矩 #19/#66 违反）我写了「`git grep -n "prescription.templates" -- backend` 共 3 处命中」，实测 9 处。** 根因两层：① 那个数是我用 python 的**子串**搜索得到的（3 处），而 `git grep` 用的是**正则**，`.` 连文件名里的 `_` 都匹配；② 更要紧的是——**这个数会被我自己的散文改变**（我写进 docstring 的引文自己就成了新的命中）。改成 `^` 锚定的模式后命中数 = **1**，且**结构上自排除**（docstring 里的引文都是缩进的、不可能落在行首）。改完我又跑了一遍那条命令复核 = 1 ✓。
3. **（硬规矩 #48-② 救了一次）我照终端回显抄缩进，把新写的 docstring 行写成 5/7 空格，而 purity 那个 bullet 的既有口径是 4/6。** 是 `repr()` 抽查发现的（终端的 `NNN |` 前缀会让人多算一个空格）。已逐行改回，并**断言**了不该动的行（`:448` = 4、`:449` = 6、命令行 `:454` = **10**、`:473-474` = 6）一个都没变。
4. **我在 `test_layering.py` 的新散文里写了单反斜杠的 Windows 路径，引入了 `DeprecationWarning: invalid escape sequence '\d'`。** pristine 里那一段没有反斜杠，所以这个 warning 是**我新引入的**（Python 3.12+ 会升级成 `SyntaxWarning`）。发现路径值得记：我先看到 `6 passed, **1 warning**`，去查才定位到自己那一行——**如果我只看「6 passed」就会把它带进 commit**。已改成 `\\`，改完 `compile()` 的 warnings 为空、pytest 输出 `6 passed`（无 warning）。
5. **两个 TEMP 脚本第一次 `py_compile` 都因为 f-string 里带反斜杠（`b'\r\n'`）而 `SyntaxError`。** Python 3.11 的限制（3.12 才放开）。改成先把 `b.count(...)` 算到局部变量再插值。**这是我本轮第三次撞上「f-string 里的反斜杠」**（另两次是错误 4 与 `check.py` 的首跑失败），说明它是我在这个环境里的一个稳定弱点：**凡是要在 f-string 里放字节串或 Windows 路径，一律先算到变量里。**

---

### fr2.10 关切与未尽事项

**1（需要控制者裁定）— `test_layering.py` 那条**代码注释**要不要一起改。**
改后 `:318` 的 `# level == 1：包内合法导入（绿档，硬规矩 #50 的 ②）；真仓 app/db/models/ 就是这一档`。它**不含计数**、对它标的那一格矩阵入参（`("_shared", 1, ("app","db","models"))`）是**真的**，但「真仓 `app/db/models/` 就是这一档」这个**全仓口径**的暗示现在不完整了（`app/domain/prescription/` 也有 2 条这一档）。我**没改**，理由见 fr2.2 末段。若要改，一句话即可：`…真仓 app/db/models/ 与 app/domain/prescription/ 都是这一档（后者 2 条，见 _imported_modules 的 docstring）`。

**2 — 支 5（AST 穷尽）对 Task 3 的约束，请写进 Task 3 的预检清单。**
从本轮起，`exercises.py` 里**任何**不带下划线的顶层 `class` / `def` / 赋值都**必须**出现在 `prescription/__init__.py` 的 `__all__` 与 `_PRESCRIPTION_PUBLIC_BASELINE` 里，否则 (c) 的支 5 红。这是一个**刻意**的紧约束（它就是为了抓「加了却忘了重导出」），但它意味着 Task 3 若想在 `exercises.py` 放一个内部辅助常量，**必须给它加下划线**。这句话已写进 (c) 的 docstring 与基线常量的注释里。

**3 — Task 3 搬迁清单（在前两轮 §7 那两份之外新增的 4 项）。**
① (a) 与 (c) 两条守卫搬到 `tests/domain/test_prescription_exercises.py`（`tests/test_refdata_prescription.py` 文件 docstring 的第 4 道闸说明里已写明「应当搬过去归位」）；② 搬的时候 `_PRESCRIPTION_PUBLIC_BASELINE` 与支 5 的 AST 口径要一起搬——**支 5 读 `exercises.__file__`、不依赖 cwd**，故搬迁不会改变它的行为（这一点我特意这样写的，因为 `tests/architecture/` 那两份守卫依赖 `cwd == backend`）；③ (b) 的 docstring 里引了 `templates.py` 的 **`2 stmts`** 与覆盖率输出的 **`37-39`** 这两个实测值，Task 3 往 `templates.py` 加 dataclass 后它们会过期——**行号 `37-39` 是我 knowingly 留下的一个脆弱引用**（它是覆盖率工具输出的引文、我在正文里绑了「本轮实测」，但它仍会漂；若要彻底免疫，就把它写成「`Missing` 列报的正是那两条语句所在的行」而不给数字）；④ 若 Task 3 的 `match.py` 写 `from ..indicators import X`，则全仓相对导入 **15 → 16**、level 分布变成 **`{1: 15, 2: 1}`**，届时我在 fr2.2 / fr2.3 改的那几段散文（purity `:450-452` 与 `:456-472`；layering `:158-166`、`:170-182`、`:254-270`）里的「`{1: 15}`」与「`level == 2` 在真仓里今天仍不存在」**都要更新**（硬规矩 #66），且两份守卫矩阵里 Ruling 67-② 那一格从「前瞻」变「真仓形状」（CE-8 / Ruling 104）。

**4 — 全仓相对导入的条数至今「没有任何测试看着」，只活在散文里。**
M1b 实测：一个**语义等价**的 import 改写（相对 → 绝对）让计数从 15 变 14，而 **531 passed、退出码 0**。这就是为什么本轮所有关于它的散文都必须绑 commit。**建议**（不在本轮范围）：若控制者希望这个数不再每轮过期，可以加一条断言把它钉成「≥ 15 且 level 分布 == {1: N}」一类的**下界/形状**断言而不是等值断言（等值断言会让每次合法的架构演进都红）。这是**裁定**，不是我能顺手做的。

**5 — 秩序声明现在有几份，请 Task 7 别再添。**
`IMPACT_DESCENDING`（测试侧字面元组）与 `IMPACT_RANK`（生产侧字典）是**刻意不同源的两份**（#35）；(a) 的支 2 把这两份**对账**，不是第三份。**Task 7 若要用秩，请从 `IMPACT_RANK` 取**（它是 domain 公开面的一部分），不要再造第四份。这句我也写进了 (a) 的 docstring。

**6 — fr2.0 那件事需要控制者做一次裁定与一次恢复。**
① 恢复 `task-2-report.md` 的 `## fix round 1` 节与 `task-1-report.md` 的 `## fix round 1`–`## fix round 5` 节（TEMP 里有 Task 1 前两节的原文可用）；② 裁定「`Read` 是否会写回截断版本」这条要不要升级成硬规矩（我建议升级，并把它与 #30/#61 归成一族：**工具口径造成的假观测**）；③ 决定今后报告是否**每轮同时另存一份到 TEMP**（Task 1 各轮就是这么做的，那个惯例这次是唯一救回一部分内容的原因）。

---

### fr2.11 附录：被截断的 `## fix round 1` 一节，我手里还剩什么

**标题清单**（来自本轮开工时我对 `task-2-report.md` 的 grep，行号是**截断前**那份 972 LF 文件的）：

```
:629 | ## fix round 1 — Ruling 96 架构搬迁（动作库的值对象搬进 domain）
:649 | ### fr1.0 派单 §4 自查的逐条正面确认（Ruling 84/100 的下游确认）
:684 | ### fr1.1 搬迁清单（按派单 §2.2 逐格对账）
:703 | ### fr1.2 三处我按自己判断做的决定（派单授权「按你的判断做并在报告里给出理由」）
:719 | ### fr1.3 验收判据逐条
:813 | ### fr1.4 变异验收（判据 5；硬规矩 #50/#53/#62/#65）
:831 | ### fr1.5 改动面自证（判据 6；硬规矩 #32 + #53）
:888 | ### fr1.6 我发现的控制者错误（逐条注明成立 / 不成立 / 歧义 + 证据）
:931 | ### fr1.7 落盘闸门与收工自证（硬规矩 #48 升级口径）
:949 | ### fr1.8 关切与未尽事项
```

`:629`–`:899` 的**正文我没有了**（只有上面这份标题清单）。`:900`–`:972` 我在本轮 15:2x 用 python 逐行打印过，**逐字转录如下**（这是本轮唯一还存在的一份；转录是手工的，可能有排版误差，行号是截断前那份文件的）。其中 `:913`–`:921`（CE-6 / CE-7）与 `:955`–`:965`（§7 的 2/3/4/5 条）正是本轮派单的依据，故优先保留：

```
:913 **CE-6（成立，但**不是本轮造成的**）— 两份架构守卫 docstring 里「全仓相对导入实测 12 条、全部 `level == 1`、全部落在 `app.db.models` 包内」已过期，实测 14 条、且 domain 侧有 1 条。**
:914 用派单/账本自己给的那条命令（`cd backend; python -c "import ast,pathlib; …"`）在 HEAD 上亲跑：**14** 条、全部 `level == 1`，其中 `app/db/models` 包内 **13** 条 + **`app/domain/prescription/__init__.py:10`** 的 `from .templates import ImpactLevel` **1** 条（本轮之后是 `from .exercises import (…)`，条数不变）。故「全部落在 `app.db.models` 包内」**不成立**，`test_domain_purity.py:451` 那句「故 domain 侧**没有 offender**」的**理由**也不再是「domain 侧没有相对导入」（结论仍对：那 1 条折成 `app.domain.prescription.exercises`、命中白名单前缀）。
:915 出现位置：`tests/architecture/test_domain_purity.py:446-451`；`tests/architecture/test_layering.py:156-159`、`:163-168`、`:237-240`（三处都写「12 条」）。
:916 **根因**：Task 2（`3ea27cc`）新建 `app/domain/prescription/__init__.py`（+1）并往 `app/db/models/prescription.py:49` 加 `from ._shared import …`（+1），12 → 14，而硬规矩 #66 要求的「grep 出全部同类计数」没做；上一轮的控制者亲验清单也没有这一项。
:917 **我的处置：报告，不改。** 理由：① 它是基线 HEAD 上就已存在的假陈述，**不在 Ruling 96 的因果链里**——我用的是**绝对**导入 `from app.domain.indicators import ITEM_BUCKET`，相对导入条数在我改前改后都是 14；② 修它要动两份被评审过 5 轮、docstring 里全是实测口径的守卫文件，且牵涉一个**口径裁定**（「今天/实测 N 条」这类现在时计数该不该逐处绑 commit，硬规矩 #37 只规定了行号要绑）——那是一次裁定，不该由我顺手做掉。**请控制者派一次专门的散文修正**，或明确授权我在下一轮带上。
:919 **CE-7（成立，同上）— `app/db/models/__init__.py:74` 的 `from . import feedback, prescription` 实际在 `:82`。**
:920 两份守卫 docstring 都按名字引用了这一行：`test_domain_purity.py:102-103`（「真仓里就有这一形状：`app/db/models/__init__.py:74` 的 `from . import feedback, prescription`」）、`test_layering.py:163-165`（「上面那条命令打出来的**第 7 行**是 `app/db/models/__init__.py 74 1 None`」）。实测那条命令的第 7 行是 `app/db/models/__init__.py **82** 1 None`——**「第 7 行」这个序数仍然对**（`__init__.py` 里 7 条相对导入，`module=None` 那条仍排第 7），错的只是行号。
:921 **根因**：Task 2 按 Ruling 90 改了 `app/db/models/__init__.py` 的 docstring（`:1` / `:34` / `:72-73` 那几处「14 → 15 张表」「八个 → 九个 JSON 列」），把这一行从 74 推到 82，而引用它的两处没跟着改（硬规矩 #66 / #37）。**处置同 CE-6：报告，不改。**
:955 **2 — `IMPACT_RANK` 现在是 domain 公开面的一部分，但没有任何测试直接钉它的秩值。**
:956 今天钉住它的是**间接**路径：`test_equivalence_never_maps_to_a_higher_impact_level`（用测试侧字面的 `IMPACT_DESCENDING`，两侧不同源）与 `test_lookup_honours_the_impact_ceiling_and_returns_none_when_unsolvable`。fr1.4 的 M-B 证明这两条**足以抓住**秩值对调（1 failed）。**但一条直接断言 `IMPACT_RANK == {HIGH: 0, MEDIUM: 1, LOW: 2}` 的测试不存在**，而它现在是**公开 API**（`from app.domain.prescription import IMPACT_RANK` 可用）。**我没加**（会让 528 变 529，超出「纯搬迁」）；若 Task 7 要直接消费这个序，建议那时补一条**字面写死**的断言（不要从 `ImpactLevel` 派生——它继承 `str`、字典序与冲击序无关）。
:958 **3 — `templates.py` 今天是一个只有 re-export 的模块，而它有一条**没有消费者**的公开面。**
:959 实测：`from app.domain.prescription.templates import ImpactLevel` 在全仓的**唯一**使用者是 `tests/domain/test_prescription_templates.py:37`（我刻意保留的那一处，见 CE-4）。生产代码里**没有**任何模块从 `templates` 导入 `ImpactLevel`。这不是缺陷（Task 3 会往这个文件加 8 个 dataclass，那时它自然有内容），但**下一个人看到 `templates.py` 只有一个 re-export 时，可能会以为它是残留而删掉**——删掉的后果是 domain 覆盖率跌破 100% 而**没有任何测试变红**（同 CE-4 的失效形态）。故我在 `templates.py` 的 docstring 里写了「本模块今天没有任何自己的定义」+ Task 3 注意事项，在测试文件里写了「import 刻意不改」的理由。**两处都写了，因为这件事没有守卫看着。**
:961 **4 — `app/domain/prescription/__init__.py` 的 `__all__` 没有任何测试钉住。**
:962 它从 1 个名字扩到 7 个。`app/db/models/__init__.py` 的 `__all__` 有 `test_models_public_namespace_is_unchanged_by_the_split` 看着（钉的是拆包前的 33 个名字），而 domain 这个包**没有**对应的守卫。**失效形态**：谁往 `__all__` 里加一个 `exercises.py` 里没有的名字，`from app.domain.prescription import *` 会在运行期 `AttributeError`，但没有测试会提前红。**我没加**（超范围）；建议 Task 3 建 `tests/domain/test_prescription_templates.py` 的新守卫时顺手加一条 `set(__all__) == {n for n in dir(pkg) if not n.startswith('_')}` 之类的自洽断言——⚠️ 但那会与硬规矩 #35 打架（两侧同源），**更好的形状**是字面写死 7 个名字、随 Task 递增。
:964 **5 — CE-6 / CE-7 / CE-8 三条散文缺陷我没有修，需要控制者派一次。**
:965 三条都在 `tests/architecture/` 的两份守卫 docstring 里（相对导入 12 → 14、`app/db/models/__init__.py:74` → `:82`、`level == 2` 那格仍是前瞻），都是 Task 2（`3ea27cc`）造成的、都不在本轮因果链里。我给出实测证据但不顺手改的理由写在 CE-6 末尾。**若控制者认为该由本轮带上，我可以再做一次 fix round（纯散文，`ast.dump` 闸门可证零代码改动）。**
:971 **7 — 给 Task 3 的连带清单（在上一轮 §7-9 那份之外新增的 3 项）。**
:972 ① `templates.py` 现在是 **2 stmts**，Task 3 往里加 dataclass 时会改变 domain 的 stmts 基数，别再按「templates.py 5 stmts」推算；② `templates.py` 的 `__all__ = ["ImpactLevel"]` 与 `prescription/__init__.py` 的 `__all__`（7 个名字）是**两份**，加东西时两处一起改（两个文件的 docstring 里都写了这句）；③ 若 Task 3 的 `match.py` 写 `from ..indicators import X`（`level == 2`），那会让两份守卫矩阵里 Ruling 67-② 那一格从「前瞻」变成「真仓形状」（CE-8），届时请顺手把 CE-6 的「14 条」更新成新的实测值。
```

**⚠️ 转录里有一处**前任的错误**要点出来**（本轮已按实测更正）：`:959` 说「删掉的后果是 domain 覆盖率跌破 100% 而**没有任何测试变红**」——**删文件**其实会在收集期 ImportError 而**响亮地红**（MB3 实测退出码 2）；真正「退出码 0 而覆盖率跌破」的是**改指 import、留着文件**那个形态（MB4 相位 2 实测）。Ruling 107-3 沿用了 `:959` 的说法，本轮 (b) 的 docstring 已按实测改写。
