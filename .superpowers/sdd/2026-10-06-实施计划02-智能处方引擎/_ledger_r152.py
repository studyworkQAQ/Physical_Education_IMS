"""Task 7 结案：账本追加 Ruling 152（含控制者错误 #148–#153 + 硬规矩 #90/#91 + sha256 回填）。"""
from pathlib import Path

P = Path(__file__).with_name("progress.md")
b = P.read_bytes()
t = b.decode("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
print(f"[before] bytes={len(b)} lines={t.count(nl)}")

BODY = """

---

## ✅ Task 7 结案（处方生成阶段接入管道 `prescription_stage.py`）

**fix round 用了 1 轮**（Ruling 145 的目标 1–2 轮 ✓）。**Critical 零遗留。Plan 01 的全部既有测试仍全绿，0 条被删、0 条断言放宽。**

### 交付与验收（全部控制者本机亲跑复核，探针 `t7_probes/_t7_verify.py` 与 `_t7_fr1_verify.py` 均入库）

| 项 | Task 6 结案基线 | Task 7 结案 |
|---|---|---|
| commit | `537683f` | **`c5599db` → `a5fd7db` → `c7f2edb` → `08db233` → `ca265ab` → `fd6a427` → `f0623b3`（fr1 代码）→ `0a56e61`（fr1 文档）**（8 个） |
| 全量 `pytest -q` | 716 passed | **750 passed**（+34） |
| 带 `--cov` | 715 passed, 1 skipped | **749 passed, 1 skipped**（那 1 个 skip 是 F1-2 核过的 `gettrace` 钩子，见下） |
| `app/domain/` 覆盖率 | 948 / Miss 0 / 274 / BrPart 0 / 100% | **951 stmts / Miss 0 / 274 branch / BrPart 0 / 100%**（`percentile.py` 94 → 97 stmts，**branch 26 不变**——条件表达式不产生分支弧，正是「逐字照 `lookup_p20` 抄」的可验证后果） |
| 表数 | 18 | **18**（本 Task 不建表）；`prescription` **15 → 16 列**（fr1 加 `label_at_generation`） |
| `input_snapshot` 顶层键 | 26 | **28**（加 `"bmi"` 原始值 + `"snapshot_muscle_p10"`） |
| `PersonInputs` 字段 | 12 | **15**（三个都**无缺省**，与既有 `snapshot_muscle_p20` 同口径 → 漏改构造点当场 `TypeError`） |
| `PIPELINE_TABLES` | 9 | **11**（加 `prescription` / `weekly_adjustment`） |
| `__all__` | 47 | **47**；`_MODELS_PUBLIC_BASELINE` **33 未动**（实测 `Exercise`/`PrescriptionTemplate`/`Prescription`/`WeeklyAdjustment` **四个都不在** `models` 的公有面上，Ruling 97 完好） |
| 扫描面 | 33（domain 14） | **34**（pipeline **8** + db 11 + domain **15**） |
| 禁区 | 三个指纹 | **逐字不变**；`git diff d498bac HEAD -- backend/data` **为空**；`golden_cases.json` **未改**（27 346 B / sha16 `8C787701EA70EF90`）；`pe.db` 不存在、`data/seed/` 0 文件 |

**控制者亲验的承重结论**：
- `_replay_cleanup` 的清单顺序**实测** = `(models.DerivedMetrics, models.StratificationResult, models.PercentileSnapshot, WeeklyAdjustment, Prescription)` —— **子表先删，P7-A4 落地** ✓
- `lookup_p10` 存在，**签名与 `lookup_p20` 逐字相同** ✓；`percentile.py` 本来就没有 `__all__`（故「不在 `__all__` 里」不是缺陷——`lookup_p20`/`lookup_p25` 也不在）；它的 import 面 = `{app.domain.indicators, app.domain.tables, collections.abc, dataclasses, enum, numpy}`，**无违规** ✓
- fr1 的新列：`label_at_generation VARCHAR(20) NOT NULL` + CHECK `ck_prescription_label_at_generation` → `label_at_generation IN ('green','insufficient_data','red','yellow')`；**`hasattr(Prescription, "LABELS") is False`** —— 值域**直接引 `StratificationResult.LABELS`，没有另立第二份词表** ✓（单一所有者）。`String(20)` 的依据实测成立：`stratification_result.label` 也是 `String(20)` + 同型 CHECK，而 `derived_metrics.trend` 的注释逐字写着「取 20 与 `stratification_result.label` 对齐」（Ruling 144）
- `_last_prescription_of` **已是纯映射**（直接读 `row.label_at_generation`），`outerjoin` 回读已删 ✓
- `prescription_stage.py` **50 707 B / 860 行**，公开面 = `PrescriptionReport` / `valid_to_of` / `active_or_needs_review` / `training_package_payload` / `profile_of` / `generate_prescriptions`
- 500 人亲跑复现了计划预测的两个数：**缺省注入 498 张/天（Z0 2 人）、零注入 500 张/天（Z0 0 人）**，全季 2490 / 2500 张，生成日恰好 5 天（28 天间隔）

### canonical sha256 的回填（P7-A6 的落地；**归 Task 9 写进 spec §1.3 的勘误**）

夹具 = 60 人 / `seed=20250828` / 缺省注入 / `D=2025-09-15`，两遍 `run_daily`、`first == second` 成立：

| 覆盖面 | 旧值（Plan 01 结案时） | 新值 | 行数合计 | 是谁改的 |
|---|---|---|---|---|
| **9 张**（Plan 01 的 `PIPELINE_TABLES`） | `fe0a44e052c7946b425515fbaaa78f09e32320917a927cd10c8947aea3abfd8f` | **`1f043f2a72153720896ed76038d2230852696e78cc4ca2406292a75e1bf4a952`** | **882**（未变） | **`c5599db`（加两个快照键）**——⚠️ 不是扩表造成的 |
| **11 张**（Task 7 之后） | — | **`2b2649add55205e668c40e287f91592c0bcfcd68599d725030a68fc2400456df`** | **942** = 882 + 60 处方 + 0 调整 | `c7f2edb` 扩表 + `f0623b3` 加列 |

⚠️ **四个值都不被任何守卫钉住**：那条测试断言的是 `assert first == second`（两次运行相等），不是与字面哈希相等。**fr1 的一次有意义的交叉验证**：只动 `prescription`（不在那 9 张里）时，**9 张那个哈希逐字未变**（仍 `1f043f2a…`），证明它与 11 张那个是两套独立的量。
⚠️ `label_at_generation` 的实测分布 = `{'green': 24, 'red': 7, 'yellow': 29}`（合计 60），与 `prescription_stage.py` 模块 docstring 里那句标签分布逐字复现。

### 性能的实测结论（F1-2）

- **不带 `--cov`**：n=6（两轮 n=3），`elapsed` = 28.61 / 28.86 / 29.05 / 29.06 / 29.59 s → **最小余量 = 60 / 29.59 = 2.03×**
- **带 `--cov=app.domain --cov-branch`**：`elapsed` = **57.25 s** → 余量 **1.05×**，被 `sys.gettrace()` 钩子**如实 skip**（钩子今天仍在，`tests/pipeline/test_backfill.py` 里 `if sys.gettrace() is not None:`）
- **⚠️ Plan 01 Ruling 228 的形状今天以 1.05× 复现并被挡住**（那次是 0.95×）。
- **本 Task 一度让它真的红到 `elapsed = 115.08 s`**，实现者定位到**两处全表扫描 + 大 JSON 列 eager 加载**，修完 `52.89 s → 28.85 s`（零注入 `28.81 s`）。**这是一次真实的性能回归，被发现并修掉了**，不是一开始就有的。
- 2.03× < 2.5× → **没有放宽断言**（放宽等于取消守卫），改为把两处优化的前后值 + **测量条件**（Windows 10 10.0.26200 / AMD64 / 16 核、CPython 3.11.1、SQLAlchemy 2.1.3、SQLite 3.39.4、pytest 9.1.1、coverage 7.16.2、本地 SQLite 文件、`elapsed` 只夹 `run_backfill`、n=3 无 trace 钩子）写进那条测试的 docstring（硬规矩 #42）。

### Ruling 152 — 实现者第 17–21 次顶回控制者，**5 处全部采纳**；5 处偏离全部追认

**主体轮的 3 处顶回（全部采纳）**：
1. **（→ 控制者错误 #149）计划要求「换处方时把上一张置 `replaced` 并关账 `valid_to`」是错的。** 实现者改成只用 `status="replaced"` 单点定「哪一张生效」。控制者认了三条理由：① 追溯性关账会让 `valid_to` **不再是该行自身数据的纯函数**（它变成「下一张处方什么时候生成」的函数），直接违反 spec §4.3「任一条结果都能离线复算」；② 触发 1/2/4/5 可以在自然到期**之前**就换处方（例如第 5 天分层标签变了），此时关账会把一个**已经写进库的值**回溯改掉，而重放的批次顺序不同就会改出不同的值；③ 与 Plan 01 `stratification_result.valid_to` 恒 NULL 是同一条裁定（「不跨批改写」）。**计划正文已同步更正（Task 7 Step 1 + Task 6 的「决定」段两处）。**
2. **`skipped_reasons` 加第四个键 `"assembly_error"`** —— 计划给的三类键（`MatchStatus.value` / `"no_trigger"` / `"insufficient_data"`）里**没有一格能装下「触发成立了但装配炸了」的人**，而不装就意味着这批学生在报表里凭空消失。
3. **装配失败不落 `status="needs_review"` 的行** —— 那一行必须带 `training_package`，写 `{}` 是**一个看起来正常的谎**（学生端会渲染出一份空训练单）。「转成 needs_review」落在报表计数 + warning 日志上。

**fr1 的 2 处顶回（全部采纳）**：
4. **（→ 控制者错误 #151，本轮最严重）派单里写「控制者本轮已经改了计划正文的 4 处」——实测 0 / 4 在树上。** 实现者改前取证：`git status --porcelain -- Document/…md` 相对 `fd6a427` **为空**，且四处原文逐字仍在（`` `valid_to` 关账 `` 1 命中、`重放翻倍测试红` 1 命中、`assembly_error` **0** 命中、表定义那一行没有 `label_at_generation`）。**控制者根本没落笔，却据此派了一件「复核」的活。** 实现者按硬规矩 #84 自己改了这 4 处 + 4 处连带（Interfaces 那行漏了 `"insufficient_data"`、「Task 6 新增的三列」抬成三列+一列、两处「三处预检更正」计数抬一格）。
5. **（→ 控制者错误 #152）派单预设 `test_models.py` 里有一条钉住 `prescription` 列数的断言**（「Task 6 加过 `len(...columns) == 15` 之类」）——**实测不存在**：`git grep -nE "len\\(.*\\.columns\\) ==" -- backend/tests` 只命中 1 处，是 Task 3 给 `PrescriptionTemplate` 的 `== 10`。实现者**刻意没有新加**一条「`prescription` 是 16 列」的守卫，理由成立：**纯计数守卫抓不到任何失效形态**（少一列会由 NOT NULL 违例 / 新测试 / canonical sha256 至少一条抓到），却会给 Plan 03 每次加列添一次改数字的活。**控制者采纳，不要那条守卫。**

**5 处偏离派单字面：全部追认**（commit 拆成 6 个且 ②③ 合并 / `valid_to` 不关账 / 变异 ② 的红条不是「重放翻倍测试」/ 500 人两个数没进测试网而是探针复量 + 报告留档 / 装配失败不落行）。fr1 另**多做 4 处**（都已在报告里声明）：一条 schema 守卫（变异实证有牙：`String(20)` → `String(16)` 时它与 Plan 01 的列宽**遍历**测试同时红）、一次额外变异、计划正文 4 处连带、以及**改掉 `prescription_stage.py` 模块 docstring 里两个首轮留下的假函数名**（`_current_prescriptions` / `_labels_at`，今天都不存在）。

### 控制者错误 #148 – #153（本轮 6 条，其中 #151 最严重）

| # | 事实 | 根因 |
|---|---|---|
| **#148** | Task 6 预检时逐个核了 `LastPrescription.microcycle_weeks` 有没有住址（那是 P6-A3 那条 Critical），**却没把 `LastPrescription` 的 5 个字段逐个对到列上**。结果 `label_at_generation` 无处可放，逼出 `outerjoin` 回读 `stratification_result` —— 而那条回读有三个失效形态（`_replay_cleanup` 会按 `batch_id` 删分层行；join 条件 `(student_id, computed_on == generated_on)` 是**跨表隐式契约、无守卫**；它让处方的触发判定依赖另一张表的行还在不在）。fr1 已加列修掉。 | 只查了「触发 3 需要的那一个字段」，没做**值对象字段 ↔ 表列**的逐个对照 |
| **#149** | 计划要求「换处方时关账 `valid_to`」——见顶回 1 | 写这条时对着「处方有有效期」这个直觉推理，没问「回溯改一个已写进库的值，重放还复现吗」 |
| **#150** | 变异 ② 的判据写「→ 重放翻倍测试红」，而**翻倍在结构上不可达**（`prescription` 有唯一约束 + `repo.upsert`）。实际红的是清单那条直接守卫。 | 写变异判据时没先问「这个失效形态在结构上可达吗」——**硬规矩 #65 的反面** |
| **#151** | **派单声称「控制者本轮已经改了计划正文的 4 处」，实测 0 / 4 在树上。** 还据此派了一件「复核」的活。 | **把「我打算改」讲成「我已经改」**。与硬规矩 #19（假数字）同族，但更危险：**复核一个不存在的改动，最省力的结论就是「没问题」**——若实现者照着派单口述以为它们对了、一个字都不查，这 4 处就永远不会被改 |
| **#152** | 派单预设一条不存在的守卫（`len(...columns) == 15`） | 与 #150 同一形状：**预设一个结构上不存在的东西** |
| **#153** | **控制者的 fr1 亲验探针**用 `read_text()` 读计划正文再数 `\\r\\n`，**Python 文本模式的通用换行会把 `\\r\\n` 翻成 `\\n`**，于是数出 **0** 并当场准备把「计划正文行尾翻成了 LF」报成一条缺陷。实测 `read_bytes()` 是 **198 423 B / CRLF 1033 / 纯 CRLF**，`git ls-files --eol` 也报 `i/lf w/crlf`（`core.autocrlf=true` 下的**正常态**）。**探针错了，文件没错。** | 与 #147 / #139 同一形状：**探针的产物被当成事实**。三次都发生在「控制者亲验」这一步——而亲验正是用来纠正实现者的那一步 |

**→ 补硬规矩 #90：派单里凡是声称「控制者已经做了 X」的，必须在派单前用 shell 取证（`git status --porcelain` / `git diff --stat` / grep 那个原文），并把取证输出贴进派单。** 依据：#151 —— 「把打算做讲成已经做」比「数字写错」更危险，因为它会让实现者去复核一个不存在的东西，而**复核一个不存在的东西最省力的结论就是「没问题」**。

**→ 补硬规矩 #91：派单里提到的每一条既有守卫，都要先 `git grep` 核实它存在，再把它写进派单；引用它时要贴出命中的那一行原文。** 依据：#152 与 #150（同一形状：预设一个结构上不存在的东西）。这是硬规矩 #65 的推广——#65 只管「变异判据要写明哪个断言分支开火」，#91 管「那个断言分支得真的存在」。

**→ 硬规矩 #89 扩写：数行尾 / 字节数一律用 `read_bytes()`，绝不用 `read_text()`**（Python 文本模式的通用换行会静默把 `\\r\\n` 翻成 `\\n`，于是「数 CRLF」恒为 0）。依据：#153。#89 原文只管「数键/字段/成员不要用正则数源码」，这一次是**同一族错误的另一半**：不是查询方式错，而是**读取方式**先把证据改掉了。

### Task 8 的入口状态

- 代码基线 **`0a56e61`** + 本轮结案 commit
- **750 passed**、domain **951 / Miss 0 / 274 / BrPart 0 / 100%**、**18 张表**（`prescription` **16 列**）、`__all__` **47**、`_MODELS_PUBLIC_BASELINE` **33（不动）**、扫描面 **34**
- SQLAlchemy **2.1.3**、Python 3.11.1（无 venv）
- ⚠️ **Task 8 要注意的三处**：① `weekly_factors_of(session, prescription_id)` 的 ORM import 走 `from app.db.models.prescription import WeeklyAdjustment`（Ruling 97，Task 6 结案时已写进 Task 8 正文，fr1 复核**仍在**）；② `WeeklySheet` 的缩放**只作用于 `weekly_volume`、不改 `hr_zone`**，而 `weekly_volume` 自 Task 5 起带 `volume_unit`（`"min"` / `"reps"` / `"unspecified"`），**缩放不得跨单位相加**；③ `WeeklyFactor` 的 `factor` 合法区间 `(0, 2]` 与 DB 的 `weekly_adjustment.factor` 列**没有对应的 CHECK** —— 这是**两层守卫、不是重复**（domain 的值对象与 DB 的列各有各的失守方式），**要在 Task 8 的正文里写明这一点**，否则下一个人会以为其中一个是冗余的。
"""

if nl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", nl)
assert "Ruling 152" not in t, "Ruling 152 已存在"
P.write_bytes((t.rstrip("\r\n") + BODY).encode("utf-8"))
c = P.read_bytes().decode("utf-8")
print(f"[after]  bytes={len(c.encode('utf-8'))} lines={c.count(nl)} "
      f"CRLF={c.count(chr(13)+chr(10))} LF={c.count(chr(10))}")
for k in ("Ruling 152", "硬规矩 #90", "硬规矩 #91", "控制者错误 #148", "控制者错误 #151",
          "控制者错误 #153", "1f043f2a72153720896ed76038d2230852696e78cc4ca2406292a75e1bf4a952",
          "2b2649add55205e668c40e287f91592c0bcfcd68599d725030a68fc2400456df"):
    print(f"  {k[:44]}: {c.count(k)}")
