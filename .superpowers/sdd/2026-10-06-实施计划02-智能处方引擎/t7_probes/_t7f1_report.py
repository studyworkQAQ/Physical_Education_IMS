"""往 task-7-report.md 追加 `## Task 7 fix round 1` 一节（python 追加，不用编辑器打开）。

行尾：报告文件实测是 LF 还是 CRLF，先量再按原样写回。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[4]
P = ROOT / ".superpowers" / "sdd" / "2026-10-06-实施计划02-智能处方引擎" / "task-7-report.md"
raw = P.read_bytes()
CRLF = raw.count(b"\r\n")
LF = raw.count(b"\n")
print(f"改前：{len(raw)} B / {LF} 行 / CRLF={CRLF}")
assert CRLF in (0, LF), (CRLF, LF)
newline = "" if CRLF == 0 else "\r\n"

SECTION = """

---

## Task 7 fix round 1

基线 `fd6a427`，分支 `feature/plan-02-prescription-engine`（未 push、未切分支、未碰 main）。
本轮修 3 项（1 Critical / 2 Important），**2 个 commit**：

| commit | 内容 |
|---|---|
| `f0623b3` | **F1-1** 加列 + 填值 + 改读法 + 那条新测试；**F1-2** 的 docstring 实测与测量条件；`test_daily.py` 的 canonical 取证表 |
| `<SHA2>` | **F1-3** 计划正文补丁（11 处替换 + 1 处计数连带）+ 本报告 |

改动面（`git diff --stat fd6a427 f0623b3`）：**6 个文件、280 insertions / 104 deletions**，
全在 `backend/`；`backend/data/` **零改动**。

### 1. F1-1（Critical）：`prescription` 补 `label_at_generation` 列

#### 1.1 实测先行（硬规矩 #89，全部运行时口径）

派单要求「`stratification_result.label` 那一列今天用的是什么长度，先实测再决定，与它保持一致」。实测：

| 量 | 实测值 | 出处 |
|---|---|---|
| `stratification_result.label` 的类型与长度 | **`String(20)`**，`nullable=False`（由 `Mapped[str]` 推出） | `StratificationResult.__table__.c.label` |
| 它有没有 CHECK | **有** | `_in_domain("label", LABELS, "ck_stratification_result_label")` |
| 那条 CHECK 的文本 | `label IN ('green', 'insufficient_data', 'red', 'yellow')` | 运行时 `str(sqltext)` |
| 值域的所有者 | `StratificationResult.LABELS`（类常量，**四个**值） | 同上 |
| 最长值 | `insufficient_data` = **17** 字符 | `max(len(v) for v in LABELS)` |
| 旁证 | `derived_metrics.trend` 也是 `String(20)`，它的列注释逐字写着「取 20 与 `stratification_result.label` 对齐：两列存的是同一族 17 字符的值」（Ruling 144） | `app/db/models/derived.py` |

→ **新列与它逐字同口径**：

```python
label_at_generation: Mapped[str] = mapped_column(String(20), nullable=False)
```

（派单给的字面形状逐字照写，含显式 `nullable=False`。）

**CHECK 也加了**，因为派单的条件成立（「除非 `stratification_result.label` 也有」——它有），
并按「照抄它的写法与约束名命名风格」：

```python
_in_domain(
    "label_at_generation",
    StratificationResult.LABELS,
    "ck_prescription_label_at_generation",
),
```

⚠️ **一处按派单的「单一所有者」要求做的取舍，值得单独交代**：值域**没有**在
`Prescription` 上另立第二份类常量，而是**直接引 `StratificationResult.LABELS`**
（`prescription.py` 因此新增 `from .derived import StratificationResult`；`derived.py`
自己也是这么引 `organisation.Student` 的，`derived` 不 import 本模块，**无环**）。
实测 `hasattr(Prescription, "LABELS") is False`。
对照 `PrescriptionTemplate.LAYERS`（那里**收窄成三个**、确实另立了一份常量）：那是必要的，
因为模板的 `layer` 真可能被人写成 `insufficient_data`、需要 DB 拒收；而**本列的写入方只有
管道**，且 Z0 闸门在 `upsert` 之前就 `continue`，故收窄没有收益、只多一个所有者。
于是值域**含** `insufficient_data` 而生产上写不进那一档 —— 这一句已写进列注释，
免得下一个人以为它是漏网的脏值。

**新列的运行时实测**：`String(20)` / `nullable=False` / `default=None` /
CHECK = `label_at_generation IN ('green', 'insufficient_data', 'red', 'yellow')`。
`prescription` 的 CHECK 从 **1** 条变 **2** 条（`ck_prescription_label_at_generation` +
`ck_prescription_status`）。

#### 1.2 `prescription` 的新列数

**15 → 16**（`len(list(Prescription.__table__.columns))`，运行时口径）。逐字：

```
['id', 'student_id', 'generated_on', 'batch_id', 'template_ref', 'microcycle_weeks',
 'label_at_generation', 'training_package', 'assembly_snapshot', 'safety_substitutions',
 'teacher_overrides', 'previous_had_overrides', 'status', 'valid_from', 'valid_to',
 'trigger_reasons']
```

新列插在 `microcycle_weeks` 之后 —— 三个「生成当时的快照」
（`template_ref` / `microcycle_weeks` / `label_at_generation`）挨在一起。
⚠️ 列序不影响 canonical sha256（`json.dumps(..., sort_keys=True)`）。

⚠️ **派单说要同步改 `test_models.py` 里「钉住 `prescription` 列数」的断言 —— 实测没有那条断言**，
见第 8 节顶回 ②。

#### 1.3 那条新测试的名字与「改前红 / 改后绿」两次实测

**名字**：
`tests/pipeline/test_prescription_stage.py::test_trigger_2_survives_the_deletion_of_that_days_stratification_row`
（放在 **B5 节「换处方：触发 2 与 `replaced`」**，因为它的主题是触发 2）。
数据形状：`red`(D1 = `2025-09-15`) 生成一张处方 → **删掉 D1 那一天的
`stratification_result` 行**（并断言 `_count(...) == 0`，坐实「真的删掉了」）→
`yellow`(D2 = `2025-09-22`) 跑第二天。

**改之前（红，逐字，`python -m pytest -q tests/pipeline/test_prescription_stage.py -k trigger_2_survives -p no:cacheprovider`）**：

```
    pair = (<app.db.models.prescription.Prescription object at 0x00000118C6EC4110>, None)
        row, label = pair
        if label is None:
>           raise ValueError(
E           ValueError: 学生 1 在 2025-09-15 没有分层结果，而他当天有一张处方（id=1）：触发 2 要比的是「生成当时的标签」，没有它就只能静默拿今天的标签去比，而那会让触发 2 变成一个每天都可能开火（或永远不开火）的假判据。两张表本该由同一批次在同一个 SAVEPOINT 里写

app\\pipeline\\prescription_stage.py:551: ValueError
=========================== short test summary info ===========================
FAILED tests/pipeline/test_prescription_stage.py::test_trigger_2_survives_the_deletion_of_that_days_stratification_row - ValueError: 学生 1 在 2025-09-15 没有分层结果，而他当天有一张处方（id=1）：触发 2 要比的是「生成当时的标签」，没有它就只能静默拿今天的标签去比，而那会让触发 2 变成一个每天都可能开火（或永远不开火）的假判据。两张表本该由同一批次在同一个 SAVEPOINT 里写
1 failed, 30 deselected in 0.72s
```

⚠️ 红的**机制正是派单预测的那一个**：`outerjoin` 读不到 → `label is None`。
（`30 deselected` 是**删掉旧守卫之前**的数；删掉之后是 `29 deselected`。）

**改之后（绿，同一条命令）**：

```
.                                                                        [100%]
1 passed, 29 deselected in 0.72s
```

断言的是（全部字面写死，硬规矩 #35）：`second.generated == 1`、
`rows[d2].trigger_reasons == ["layer_changed"]`（即 `TriggerReason.LAYER_CHANGED.value`
在里面，且**只有**它 —— D2 距 D1 整 7 天 < 4×7，触发 3 不成立；`bare` 夹具没有采集行，
触发 4 对 `None` 短路；触发 5 在管道侧恒 `False`）、
`rows[d2].label_at_generation == "yellow"`、`rows[AS_OF].label_at_generation == "red"`、
`rows[AS_OF].status == "replaced"`、`rows[d2].status == "active"`。

#### 1.4 本轮唯一一处**删**测试（把理由写全）

删掉的是首轮的
`tests/pipeline/test_prescription_stage.py::test_a_prescription_whose_stratification_row_is_gone_fails_loudly`。

* 它钉的是「触发 2 的比较对象查不到 → `_last_prescription_of` 响亮抛 `ValueError`」。
* 那个失效形态的**前提**是「标签只能 `outerjoin` 回读同一天的 `stratification_result`」。
  F1-1 之后标签是处方行自己的一个 **NOT NULL、无缺省**的列 → **前提消失** →
  那个 `ValueError` 分支**结构上不可达**（与硬规矩 #39「不可达的分支不留」一致）。
* 取代它的新测试用的是**同一个数据形状**，断言的是**相反**的结论：触发 2 **仍然成立**、
  整批不回滚。这不是「削弱守卫」，而是把守卫从「失败要响」升级成「根本不该失败」。
* 删掉之后「不许为空」这件事**没有失去守卫**：它搬到了
  `tests/db/test_models.py::test_prescription_label_at_generation_shares_its_domain_with_the_label_column`
  （漏传 → `IntegrityError`，消息里含 `prescription.label_at_generation`；
  写 `"blue"` → `IntegrityError`，消息里含 `ck_prescription_label_at_generation`）。
* 原地留了一段**注释**交代这次取代（不留下一个「为什么这里少了一条测试」的谜）。

#### 1.5 实现侧的三处改动

1. `generate_prescriptions` 的 upsert 值字典加 `"label_at_generation": label` ——
   `label` 就是本循环手上 `result.label`（当天刚写好的 `stratification_result.label`），
   **零额外查询**，与派单的要求逐字一致。
2. `_previous_prescriptions`：**删掉那个 `outerjoin`**，签名从
   `-> dict[int, tuple[Prescription, str | None]]` 变成 `-> dict[int, Prescription]`，
   `load_only(...)` 从 6 个小列变 **7** 个（多留 `label_at_generation`）。
   AST 复核：该函数里 `ast.Attribute` 的名字集合**已无 `outerjoin`**、
   源码里也已无 `StratificationResult`（`join` 仍在 —— 那是与 `latest` 分组子查询的连接，
   是「取每人最新一张」的机制，不是跨表回读）。
   ⚠️ 顺带少一张表的连接：整学期回放（500 人 ×112 业务日）不再逐日碰
   `stratification_result`（那张表学期末 56 000 行、每行约 2 KB 的 `input_snapshot`）。
3. `_last_prescription_of(row)`：读 `row.label_at_generation`，删掉 `ValueError` 分支。
   它因此变成一个**纯映射**、不再碰库，也就不再属于模块 docstring「异常分层」的第 2 档
   （那一档的清单已同步改掉，见 1.6）。

#### 1.6 变异取证（硬规矩 #83）

前后 `shutil.rmtree(__pycache__, ignore_errors=True)` + `PYTHONDONTWRITEBYTECODE=1` +
`-p no:cacheprovider`，跑完立刻还原（还原后复核：文件 **50 298 B**、`String(20)` 命中 1、
`String(16)` 命中 0）：

| 变异 | 红了哪几条 | 结论 |
|---|---|---|
| 新列 `String(20)` → `String(16)`（17 字符的 `insufficient_data` 塞不下） | `test_string_column_widths_fit_their_value_domains`（Plan 01 那道**遍历**测试）+ `test_prescription_label_at_generation_shares_its_domain_with_the_label_column` → **`2 failed, 58 passed`** | 新列**自动被那道遍历测试覆盖**（它带 CHECK，故 `_in_domain_columns()` 反解得出值域）—— 与 `Exercise.ref` / `template_ref` 那几列「没有 CHECK → 不被覆盖 → 要另找地方钉」（P2-A5 / P3-A5）**不同档** |
| 还原 | `60 passed` | — |

⚠️ **计划正文的「变异 ⑤」不需要另跑**：我在计划里补的那条
（「把 `_last_prescription_of` 改回 `outerjoin` 读 `stratification_result.label` →
新测试当场红」）**就是 1.3 那次改前红的实测状态**，取证已在手，不必再制造一次。

### 2. F1-1 的连带：canonical sha256 的新值

派单点名要这两个值（控制者要拿它回填账本与 spec §1.3）。`canonical_dump` **逐字复用**
`tests/pipeline/test_daily.py` 的那一个（import 它，不复制第二份），夹具形状逐字复刻
`test_rerunning_the_same_business_date_reproduces_every_table`（`CFG`：60 人 /
`seed=20250828` / 缺省注入，`D = 2025-09-15`），**两遍 `run_daily`**，n=1：

| 表集合 | sha256 | 行数合计 | 与首轮相比 |
|---|---|---|---|
| **9 张**（Plan 01） | `1f043f2a72153720896ed76038d2230852696e78cc4ca2406292a75e1bf4a952` | **882** | **逐字未变** |
| **11 张**（Task 7） | `2b2649add55205e668c40e287f91592c0bcfcd68599d725030a68fc2400456df` | **942** | **变了**（首轮是 `05c5b2aa4ef2c68d00edf553760fee7cbecb71487108e2e2a3752e7e504d5816`） |

两个哈希都在**两遍运行之间逐字相同**（探针里 `assert (h_first, rows_first) == (h_second, rows_second)`，
两档各断言一次）。

**9 张为什么没变**：本轮只动 `prescription` 一张表（加一列），而它**不在**那 9 张里
（9 张 = `fitness_test_batch / fitness_test_result / body_composition / interest_survey /
percentile_snapshot / derived_metrics / stratification_result / daily_sync_run / cleaning_log`）。
这是一次**有意义的交叉验证**：它坐实了 F1-1 没有顺手改到 Plan 01 的任何一张表。
**11 张为什么变了**：`prescription` 的每行多了一个键（`sort_keys=True` 之后字节串不同）。
**行数合计不变**（942 = 882 + 60 张处方 + 0 条周微调）—— 加的是**列**不是**行**。

逐表行数（11 张，本轮实测）：

```
fitness_test_batch           4      derived_metrics             60
fitness_test_result        240      stratification_result       60
body_composition           240      daily_sync_run               1
interest_survey            120      cleaning_log               133
percentile_snapshot         24      prescription                60
                                    weekly_adjustment            0
```

`prescription.label_at_generation` 的实测分布 = `{'green': 24, 'red': 7, 'yellow': 29}`
（合计 60）—— 与 `prescription_stage.py` 模块 docstring 里那句「60 人夹具在
`D = 2025-09-15` 上的标签分布 `{yellow: 29, green: 24, red: 7}`」**逐字复现**，
即新列填的确实是当天的分层标签、且 0 个 `insufficient_data`（Z0 那一档在 60 人夹具下是 0 人）。

⚠️ **这四个值都不被守卫**（那条测试刻意只断言 `first == second`，硬规矩 #35），
它们是一次取证记录。`test_daily.py` 的 docstring 取证表已按此更新（并把「过期两次」
抬成「过期三次」，逐个列出三次成因）。

### 3. F1-2：`test_backfill_500_students_under_60_seconds` 的余量

#### 3.1 三次**不带** `--cov`（派单点名的命令）

`python -m pytest -q tests/pipeline/test_backfill.py -k under_60`（加 `-p no:cacheprovider --durations=1`），
三次都 **`1 passed, 6 deselected`**：

| # | `--durations` 的 `replay` setup 墙钟 | 整条命令墙钟 |
|---|---|---|
| 1 | `30.10s setup` | `1 passed, 6 deselected in 30.65s` |
| 2 | `30.65s setup` | `1 passed, 6 deselected in 31.00s` |
| 3 | `30.59s setup` | `1 passed, 6 deselected in 31.13s` |

⚠️ **setup 墙钟 ≠ 被断言的那个 `elapsed`**：`replay` 这个 module 级 fixture 的 setup
= `seed_database`（约 0.4 s）+ `run_backfill`（= `elapsed`）。派单要的是**三个 `elapsed`
值逐字**，而那条测试**不打印**它（它只在 skip 消息里打印，而 skip 只在有 trace 钩子时发生），
故另写探针**逐字复刻 `replay` 的 fixture 体**（同 `CFG` 500 人 / `seed=20250828`、
同 `START..END`、同「本地 SQLite 文件」而非 `:memory:`、同 `time.perf_counter` 夹住
`run_backfill` 那一段），并在探针开头 `assert sys.gettrace() is None`：

| # | `elapsed`（逐字） | 余量 `60 / elapsed` |
|---|---|---|
| 1 | **28.86 s** | 2.08× |
| 2 | **29.05 s** | 2.07× |
| 3 | **29.59 s** | **2.03×** |

**最小余量 = `60 / 29.59` = 2.03×**。（本轮先跑过一次同样的 n=3，得到
`min = 28.61 / max = 29.06`（其中第 3 次逐字 `29.00 s`）、最小余量 **2.06×**；
两次 n=3 合计 6 个样本，**最坏值就是 29.59 s / 2.03×**，故报告以它为准。）

#### 3.2 一次**带** `--cov`

`python -m pytest -q tests/pipeline/test_backfill.py -k under_60 -p no:cacheprovider
--cov=app.domain --cov-branch -rs --durations=1`：

```
59.09s setup    tests/pipeline/test_backfill.py::test_backfill_500_students_under_60_seconds
SKIPPED [1] tests\\pipeline\\test_backfill.py:182: 检测到 trace 钩子（coverage / debugger）：本次量到的回放墙钟是 57.25 s，而 spec §1.3 的「< 60 秒」指的是**生产墙钟**。…
1 skipped, 6 deselected in 59.91s
```

* `elapsed` = **57.25 s**（逐字取自 skip 消息，那正是断言会看到的那一个量）→ 余量
  **`60 / 57.25` = 1.05×**，**远低于** 2× 线。
* **`sys.gettrace()` 钩子今天仍在、仍生效**（派单点名要核的这件事）：
  `git grep -n "gettrace" -- backend/tests/` → **1 命中**，
  `backend/tests/pipeline/test_backfill.py:181`（`if sys.gettrace() is not None:`，
  skip 出自 `:182`）。Plan 01 的 Ruling 228 那次教训（带 `--cov` 时余量 0.95×）
  **今天以 1.05× 复现**，而它被这个钩子如实挡住 —— 钩子不是装饰。

#### 3.3 处置（派单 F1-2 第 3 条）

最小余量 **2.03× < 2.5×**，故**没有放宽断言**（放宽等于取消守卫），改为把两处优化的
实测前后值 + 测量条件写进那条测试的 docstring（硬规矩 #42 要求写下测量条件）：

```
接入处方阶段、未优化          52.89 s（另一次亲跑量到 115.08 s → 本条当场红）
两处优化之后（缺省注入）      28.85 s   → 余量 2.08×
两处优化之后（零注入）        28.81 s
fix round 1 复测（n=3）       28.86 / 29.05 / 29.59 s → 最小余量 2.03×
fix round 1 带 --cov（n=1）   57.25 s → 余量 1.05×，被 gettrace 钩子如实 skip
```

两处优化（都在 `prescription_stage.py`）：**①** 主查询**同时**按 `batch_id` 过滤
（那一列 `index=True`）—— 只按 `computed_on` 单列过滤用不上 `(student_id, computed_on)`
那条唯一索引（它以 `student_id` 打头）→ 全表扫描，而 `stratification_result` 到学期末
56 000 行 × 约 2 KB 的 `input_snapshot`，112 天累计约 310 万行扫描；
**②** 上一张处方的预取用 `load_only(...)` 把 4 个大 `JsonText` 列延迟加载
（`training_package` 是 4 周 ×4 课 ×3 block 的嵌套字典，逐人逐日 eager 加载 ≈ 56 000 次
大 JSON 解析，而本阶段一个字节都不读它）。

测量条件（已逐字写进 docstring）：Windows 10（10.0.26200）/ AMD64 /
Intel64 Family 6 Model 197 / 16 核，CPython 3.11.1、SQLAlchemy 2.1.3、SQLite 3.39.4、
pytest 9.1.1、coverage 7.16.2；**本地 SQLite 文件**（非 `:memory:`）；
`elapsed` 只夹 `run_backfill`，**不含** `build_dataset` / `write_csv` / `seed_database`；
n=3 独立干净跑、不带 `--cov`、无 trace 钩子；带 `--cov` 那一行是 n=1 且必然被 skip。

⚠️ **仍然报为关切**（与首轮关切 2 同一条，数字按本轮更新）：余量 **2.03×** 只是刚过
硬规矩 #42 的 2× 线，而**本机墙钟极差本来就大**（同一个夹具在优化前量到过 52.89 s 与
115.08 s）；且它**抓不到「慢但没超 60 s」**—— 处方阶段若再退化 2×（到约 58 s）本条照样绿。
F1-1 删掉的那次跨表连接是**往好的方向**动（少一张表的连接），本轮 6 个样本
28.61–29.59 s 与首轮的 28.85 s 在同一个噪声带里，**看不出可归因于 F1-1 的位移**。

### 4. F1-3：计划正文的同步（硬规矩 #84）

#### 4.1 ⚠️ 复核结论：控制者说自己本轮改了 4 处，**实测 0 / 4 在树上**

改前取证（探针 `t7_probes/_t7f1_plan_precheck.py`，在 `HEAD = fd6a427` 上）：

```
=== 改前：计划正文实测命中次数 ===
  更正① Task7 Step1 的『valid_to 关账』               1     ← 未改（应 0）
  更正① Task6 决定的『并关账 valid_to』                1     ← 未改（应 0）
  更正② 变异②的『重放翻倍测试红』                      1     ← 未改（应 0）
  更正③ 表定义里有没有 label_at_generation             5     ← 5 处全是**别处**的引用，表定义那一行没有
  更正④ skipped_reasons 的 assembly_error             0     ← 未改（应 ≥1）
  补① Task8 的 WeeklyAdjustment import 路径           1     ← **在**（无需改）
  补① Task8 的 weekly_factors_of                      1     ← **在**（无需改）

git status --porcelain -- Document/2026-10-06-实施计划02-智能处方引擎.md
  -> ''  (空 = 相对 HEAD 未改动)
  HEAD = fd6a427
  文件 190726 B / 1023 行
```

`git status` 对那个文件**为空**、且 4 处原文**逐字仍在** → 那 4 处更正**一处都没落笔**。
（更正③ 的 5 处命中全在别处：`LastPrescription` 的字段清单、触发 2 的判据表、
Task 6 的测试名 `test_layer_change_compares_against_the_label_at_generation`、
§14 补项 #37 —— **`prescription` 表定义那一行没有它**。）

#### 4.2 逐处结论 + 我改了什么（共 **11** 处替换 + 1 处计数连带）

| # | 派单点名的那一处 | 复核结论 | 我做的更正 |
|---|---|---|---|
| ① | Task 7 Step 1「旧处方 `status` 变 `replaced`、**`valid_to` 关账**」 | **错**（未改） | 改成「**`valid_to` 不改写**」+ 标出**控制者错误 #149** + 指回 Task 6 那一条；并把 F1-1 的新测试写进 Step 1 的清单（含「加列之前必须红、之后必须绿」与「它取代了哪一条」） |
| ①′ | **同一事实在 Task 6「决定」里还有一处**：「**换处方时把上一张置 `replaced` 并关账 `valid_to`**」（硬规矩 #66：一个事实变了要 grep 出全部同类陈述） | **错**（未改，且派单没点这一处） | 改成「置 `replaced`，但**不改写**它的 `valid_to`」+ 三条理由（`valid_to` 必须是该行自身数据的纯函数 / 触发 1/2/4/5 会在自然到期前换处方，回溯改写会随重放批次顺序改出不同的值 / 与 Plan 01 `stratification_result.valid_to` 恒 NULL 同一条裁定）+ 保留「与 Plan 01 不矛盾」那半句 |
| ② | Task 7 变异 ②「把 `_replay_cleanup` 的清单里 `prescription` 删掉 → **重放翻倍测试红**」 | **错**（未改） | 改成「→ **`test_replay_cleanup_covers_prescription_and_weekly_adjustment` 当场红**」+ 标出**控制者错误 #150**（那个失效形态**在结构上不可达**：唯一约束 + `repo.upsert`，翻倍写不进去）+ 一句教训（与硬规矩 #65 同源：写变异判据之前先问「这个失效形态在结构上可达吗」）；并**追加变异 ⑤**（改回 `outerjoin` → 新测试红） |
| ③ | Task 6「决定」里 `prescription` 表的字段清单 | **错**（未改） | 清单末尾加 **`label_at_generation: String(20), nullable=False` + CHECK**，并写明：15 → **16** 列、#148 的形状、与 P6-A3 同构的理由、列宽与 CHECK 与 `stratification_result.label` 同口径、值域**引 `StratificationResult.LABELS`**（单一所有者）、不加它的三个失效形态 |
| ④ | Task 7「决定」里 `skipped_reasons` 的键 | **错**（未改） | 补第四个键 **`"assembly_error"`** + 理由（三类键里没一格能装下「触发成立了但装配炸了」的人，不装就等于让这批学生在报表里凭空消失）+ **顶回 ③**（装配失败**不落** `status="needs_review"` 的行，`training_package = {}` 是一个看起来正常的谎；「转 needs_review」落在报表计数 + `skipped_reasons` + `warning` 日志上） |
| ④′ | **同一事实在 Interfaces 那一行还有一处**：`skipped_reasons: dict[str, int]`（键是 `MatchStatus.value` 或 `"no_trigger"`） | **本来就漏**（连 `"insufficient_data"` 都没写） | 改成四类键都列出 + 指回「决定」那一条 |
| ③′ | **同一事实在 Task 7「⚠️ Task 6 新增的三列必须由本 Task 填」还有一处** | **未改** | 标题改成「三列 + fix round 1 追加的一列」，并在 `previous_had_overrides` 之后插一条 `prescription.label_at_generation` 的填法（来源 = 当天刚写好的 `stratification_result.label`，**不需要额外查询**；`_last_prescription_of` 从这一列读、不再 `outerjoin`） |
| 计数 | Task 6「决定」与 `models/prescription.py` 的类 docstring 各有一处「spec §4.4 **+ 三处预检更正**」 | 加了一列 → 计数过期（硬规矩 #66） | 两处都改成「+ 三处预检更正 **+ fix round 1 的一处追加**（F1-1，控制者错误 #148）」 |
| 补① | **Task 8** 的 `weekly_factors_of(session, prescription_id)` 那条 import 路径 | **✅ 在，无需改** | 逐字复核：`⚠️ **ORM 行的 import 路径同 Task 7**：` `from app.db.models.prescription import WeeklyAdjustment` `（Ruling 97：它**不在** `app.db.models` 的公有导入面上）` —— 命中 1 处，且 `weekly_factors_of` 也命中 1 处 |
| 补② | **Task 9** 的 13 例要不要断言 `label_at_generation` | 见下面 4.3 | 已写进 Task 9 Step 1 |

#### 4.3 Task 9 的判断：**同意「要」，但要写清它钉得住什么、钉不住什么**

派单要我给判断，控制者倾向「要」。**我同意**，理由是控制者那一条：它是触发 2 的
**唯一判据**，而 Task 9 是最后一个能钉住它的地方。⚠️ 但**无保留地同意会立一条看起来强、
其实弱的守卫**（硬规矩 #39 的反面），故写进 Task 9 正文的版本带四条边界：

* **钉得住**：处方行上那一列填的是**当天分层结果的那一个标签**，且与黄金用例里已逐条
  人读确认的 `expected.label` **逐字相等**（两侧不同源：一侧是 fixture 的字面量、
  一侧是库里的列）。抓的是「填错了来源」—— 填成 `dominant_bucket`、填成昨天的标签。
* **钉不住**：**触发 2 本身** —— 黄金用例是**单日**的，而触发 2 要两天。故它**不是**
  `test_trigger_2_survives_the_deletion_of_that_days_stratification_row` 的替代，两条**并列**。
* ⚠️ `insufficient_data` 那一例**没有处方**（Z0 闸门），故 13 例里只有 **12** 例能断言它。
* ⚠️ **它与 `template_id` 不是两份独立的证据**：对**已匹配**的处方，`label_at_generation`
  与 `template_ref` 的前三字符（`RED` / `YEL` / `GRN`）**恒等** —— 匹配器就是按
  `Layer(label)` 选模板的。它多出来的那一份价值是「与 `expected.label` 这个**已人读的
  字面量**同源比对」，而不是「多一个字段」。**别把它写成两条互相印证的守卫。**

### 5. 最终验收

| 项 | 首轮（`fd6a427`） | **fix round 1（`f0623b3` + docs）** |
|---|---|---|
| 全量 passed（**不带** `--cov`） | 749 | **750** |
| 全量（**带** `--cov=app.domain --cov-branch`） | 748 passed, 1 skipped | **749 passed, 1 skipped** |
| `app/domain` 覆盖率 | 951 / Miss 0 / 274 / BrPart 0 / 100% | **951 / Miss 0 / 274 / BrPart 0 / 100%**（逐字未变；本轮不新增 domain 代码，`triggers.py` 一个字没动） |
| `prescription` 列数 | 15 | **16** |
| 全库表数 | 18 | **18** |
| `PIPELINE_TABLES` | 11 张 | **11 张** |
| `app.domain.prescription.__all__` | 47 | **47** |
| 扫描面 | 34（domain 15 + pipeline 8 + db 11） | **34（15 + 8 + 11）** |
| `models` 公有导入面 | 33，四个 Plan02 表类都不在里面 | **33**，`Exercise` / `PrescriptionTemplate` / `Prescription` / `WeeklyAdjustment` **仍都不在里面**（Ruling 97 未被破坏；本轮新增的 `from .derived import StratificationResult` 在**子模块**里，不经 `import *` 进包面） |
| `PersonInputs` 字段数 | 15 | **15** |
| `lookup_p10` / `lookup_p20` 签名 | 逐字相同 | **逐字相同**（本轮未动 `percentile.py`） |
| `_replay_cleanup` 清单顺序 | `(DerivedMetrics, StratificationResult, PercentileSnapshot, WeeklyAdjustment, Prescription)` | **逐字未变**（AST 口径复核，子表先删，P7-A4 仍在） |
| `prescription_stage.py` | 50 675 B / 866 行 | **50 707 B / 860 行**（删掉那个 `ValueError` 分支与 `outerjoin`，加上新列的注释与填值） |
| `prescription_stage.py` 公开面 | `PrescriptionReport` / `valid_to_of` / `active_or_needs_review` / `training_package_payload` / `profile_of` / `generate_prescriptions` | **逐字未变**（AST 口径） |
| 三个禁区指纹 | `D2C8E539E2FA0029` / `3DE598AF38631209` / `822CB86A5E998301` | **逐字不变**（21 412 B / 22 739 B / 8 245 B） |
| `golden_cases.json` | 27 346 B / sha16 `8C787701EA70EF90` | **未改**（27 346 B / sha16 `8C787701EA70EF90`） |
| `backend/pe.db` | 不存在 | **不存在** |
| `backend/data/seed/` | 0 文件 | **0 文件** |
| `git diff fd6a427 HEAD -- backend/data` | — | **空** |

Plan 01 的全部既有测试仍全绿（750 里含它们；带 `--cov` 时那 1 skipped 就是 F1-2 那条）。

### 6. 2 个 commit 的 sha

* **`f0623b3`** —— `fix: Plan02 Task7 fix round 1 F1-1 —— prescription 加 label_at_generation 列（控制者错误 #148）`
  （6 个文件：`app/db/models/prescription.py`、`app/pipeline/prescription_stage.py`、
  `tests/db/test_models.py`、`tests/pipeline/test_prescription_stage.py`、
  `tests/pipeline/test_daily.py`、`tests/pipeline/test_backfill.py`）
* **`<SHA2>`** —— `docs:` F1-3 的计划正文补丁（11 处替换 + 1 处计数连带）+ 本报告

### 7. 我没按本派单做的地方（**4 处，全是「多做了」，没有「少做」）**

1. **多加了一条 schema 守卫**：派单说 F1-1 的那条测试是「本项**唯一**的可执行判据」。
   我另加了
   `tests/db/test_models.py::test_prescription_label_at_generation_shares_its_domain_with_the_label_column`。
   理由：那两条测试的**主语不同**（硬规矩 #56）—— 新测试守的是**行为**
   （删掉分层行后触发 2 仍成立），这条守的是 **schema**（同宽 / 同值域 / NOT NULL 无缺省 /
   两条 CHECK 的值域部分逐字相同 / 漏传与脏值各炸一次）。而且 Task 6 的每一列都有这样一条
   （`status` / `template_ref` / `microcycle_weeks` / `previous_had_overrides` / `valid_to`），
   不加就是这一列独缺。变异实证它有牙（1.6）。
2. **多跑了一次变异**（1.6 的 `String(20)` → `String(16)`）：派单本轮没要求变异，
   但它顺带证明了「新列**自动**被 Plan 01 那道列宽遍历测试覆盖」这件事 —— 那正是
   P2-A5 / P3-A5 两次踩过的坑（没有 CHECK 的列不被覆盖），值得一次实证。
3. **改了计划正文里派单没点名的 4 处**（表 4.2 的 ①′ / ④′ / ③′ / 计数）：
   都是硬规矩 #66 的连带（同一个事实的另一处陈述）。**没有**改任何与本轮无关的散文。
4. **改了 `prescription_stage.py` 模块 docstring 里两处失效引用**
   （`_current_prescriptions` / `_labels_at` —— 这两个函数今天都不存在，是首轮留下的假名字）：
   它们就在「异常分层」第 2 档那一句里，而那一句因为 `_last_prescription_of` 变成纯映射
   **必须**改（它不再属于「基础设施异常」那一侧），故顺手把同一句里的两个假名字改对。
   ⚠️ 严格说这是纯散文精度问题（Ruling 145 允许记进待清扫不返工），但它与必须改的那半句
   **在同一行**，留着就是一个我自己刚写下的假名字（硬规矩 #19）。

**少做的地方：0 处。** 派单的 F1-1 / F1-2 / F1-3 三项要求逐条都做了；
F1-2 第 4 条（「若最小余量 < 2.0× 就停下来报回控制者」）**未触发**（2.03× > 2.0×），
故按第 3 条走（写进 docstring），没有停下来。

### 8. 我认为本派单错了的地方（顶回 —— 前 19 次全对，这是第 20、21 次）

**顶回 ①：派单说「控制者本轮已经改了计划正文的 4 处」—— 实测 0 / 4 在树上。**

* 证据（4.1 那份改前取证）：`git status --porcelain -- Document/…md` **为空**
  （相对 `HEAD = fd6a427` 一个字节都没动），而 4 处原文**逐字仍在**
  （`` `valid_to` 关账`` 1 命中、``并关账 `valid_to` `` 1 命中、`重放翻倍测试红` 1 命中、
  `assembly_error` **0** 命中）。
* 这不是「改错了」，是**没落笔**。形状与硬规矩 #19（假数字）同族：**把「我打算改」
  讲成「我已经改」**，而派单还据此给我派了一件「复核」的活 —— 复核一个不存在的改动，
  最可能的结局是我照着派单的口述**以为**它们对了、于是一个字都不查。
  → 建议记为**控制者错误 #151**。
* 我按硬规矩 #84 自己改了（11 处替换 + 1 处计数连带），逐处见 4.2。

**顶回 ②：派单预设 `test_models.py` 里有一条「钉住 `prescription` 列数」的断言 —— 实测没有。**

* 派单原文：「⚠️ `test_models.py` 里若有钉住 `prescription` 列数的断言（Task 6 加过
  `len(...columns) == 15` 之类的守卫），**同步改**。」
* 实测：`git grep -nE "__table__\\.c\\) ==|columns\\)\\) ==|len\\(.*\\.columns\\) ==" -- backend/tests`
  **只命中 1 处**，是 `assert len(PrescriptionTemplate.__table__.c) == 10, "Task 3 结案时是 10 列，本 Task 不动它"`
  —— 那是 **Task 3 给另一张表**加的，本轮不动它。`Prescription` **从来没有**列数守卫。
* 这与**控制者错误 #150 是同一个形状**：派单预设了一个**结构上不存在**的东西
  （#150 预设了一个结构上不可达的失效形态，本条预设了一条不存在的断言）。
  → 建议记为**控制者错误 #152**，并考虑把硬规矩 #65 的扩写从「变异判据」推广到
  「**派单里提到的每一条既有守卫，都要先 `git grep` 核实它存在**」。
* ⚠️ **我刻意没有去新加一条「`prescription` 是 16 列」的守卫**：纯计数守卫抓不到任何
  失效形态（少一列会由 NOT NULL 违例 / 1.3 那条新测试 / canonical sha256 三条里的
  至少一条抓到），而它会给 Plan 03 每次加列都添一次「改一个数字」的活。
  派单是**条件句**（「若有…同步改」），条件为假 → 不动，故这不算偏离；
  **若控制者要它，请明说**，我下一轮加。

### 9. 待清扫（纯散文精度，本轮按 Ruling 145 不返工）—— **3 条**

1. **`models/prescription.py` 的模块 docstring 只有「加**表**」的同步清单，没有「加**列**」的。**
   本轮实测加一列要动 **3** 处：`tests/db/test_models.py` 的 `_in_domain_columns()` docstring
   里那个「今天 **N** 列」的计数（带 CHECK 的列才进那份计数）、同文件的
   `_prescription_fields()`（NOT NULL 且无缺省的列一律要显式给值）、以及
   `tests/pipeline/test_daily.py` 的 canonical sha256 取证值（**只有**加进
   `PIPELINE_TABLES` 那 11 张表的列才会触发它，而这一点今天没有任何文字交代）。
   那段清单的开头写着「⚠️ **Plan 03 再加表时，下面这套同步动作要重跑一遍**」——
   Plan 03 大概率也要**加列**（教师端 CRUD），故建议补一小节「加列时」。
2. **`_previous_prescriptions` docstring 第 2 条里那句「不延迟时整学期回放多花约 `30 s`
   （`52.89 s` vs 基线 `28.4–34.0 s`）」自相矛盾**：它自己括注的两个数算出来是
   **约 24 s**（52.89 − 28.85），不是 30 s。首轮写的时候那个「30 s」大概是
   `load_only` **单独**一项的贡献（另一项是 `batch_id` 索引过滤），但正文没这么说，
   读起来就是一个与自己括注对不上的数（硬规矩 #19 的形状）。本轮未改（纯散文，
   且改它需要重跑一次「只加 `load_only`、不加 `batch_id` 过滤」的对照，不值一轮的时间）。
3. **`test_backfill.py` 那条测试 docstring 的**开头**两句仍然印着 Plan 01 的值、且没有时间限定词**：
   「**两种读法都达标**（Ruling 172）：整学期 112 天 **17.98–18.92 s**（3.2–3.3× 余量…)」
   —— 那是**接入处方阶段之前**的量，今天是 28.86–29.59 s。本轮补的那一段（3.3）
   **在它下面**，且开头就写了「⚠️⚠️ 上面那张表是 Plan 01 的口径」，故**信息不缺、
   但顺序上先读到过期值**。建议下一轮把那一句加上「Plan 01 结案时」的限定词
   （本轮没改：它是 Plan 01 的取证记录，改它等于改写别人的实测，而加限定词又要连带
   改 `replay` fixture docstring 里的同一组数，超出本轮范围）。
"""

with P.open("a", encoding="utf-8", newline=newline) as f:
    f.write(SECTION)

raw2 = P.read_bytes()
LF2 = raw2.count(b"\n")
print(f"改后：{len(raw2)} B / {LF2} 行 / CRLF={raw2.count(bytes([13, 10]))}")
print(f"新增：{len(raw2) - len(raw)} B / {LF2 - LF} 行")
txt = raw2.decode("utf-8")
print("BOM?", txt.startswith("\ufeff"))
for probe in ("## Task 7 fix round 1", "f0623b3", "2b2649add55205e6", "test_trigger_2_survives_the_deletion_of_that_days_stratification_row",
              "控制者错误 #151", "控制者错误 #152", "28.86 / 29.05 / 29.59", "57.25"):
    print(f"   {probe[:60]!r:64s} 命中 {txt.count(probe)}")
print("   '## ' 一级节数 =", txt.count("\n## "))
