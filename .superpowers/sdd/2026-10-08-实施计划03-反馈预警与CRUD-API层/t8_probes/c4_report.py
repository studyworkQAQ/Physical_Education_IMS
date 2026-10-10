"""T8 报告写盘：用 python 写 UTF-8 无 BOM，写完用 read_bytes() 复核行尾与字节数。"""
import pathlib

PLAN = pathlib.Path(__file__).resolve().parents[1]
TARGET = PLAN / "task-8-report.md"

BODY = r"""# Plan 03 Task 8 结案报告：§8.5 班级周报 + 大屏/首页聚合读接口 + 教师端训练单变体

**分支** `feature/plan-03-feedback-alert-crud-api` · **基线** `6127fc7` · **HEAD** 见第 ⑧ 节
**fix round：0**（账本 Ruling 1 + Ruling 5 的目标是 0–1 轮）
**顶回控制者：4 处**（第 ⑦ 节逐条）· **没按派单做的地方：5 处**（第 ⑦ 节逐条）

---

## ① 环境与基线复现

### 1.1 import 冒烟（硬规矩 #73，开工第一件事）

```
python -c "import sqlalchemy, fastapi, uvicorn, httpx, pydantic, yaml; print(...)"
→ 2.1.3 0.141.1 0.54.0 0.28.1 2.13.5 6.0.3
```

| 包 | 实测 | 派单 | 一致 |
|---|---|---|---|
| Python | 3.11.1（无 venv） | 3.11.1 | ✓ |
| SQLAlchemy | **2.1.3** | 2.1.3 | ✓ |
| FastAPI | **0.141.1** | 0.141.1 | ✓ |
| uvicorn | 0.54.0 | 0.54.0 | ✓ |
| httpx | 0.28.1 | 0.28.1 | ✓ |
| Pydantic | **2.13.5** | 2.13.5 | ✓ |
| PyYAML | 6.0.3 | 6.0.3 | ✓ |

无 `ImportError: DLL load failed`，未触发派单的停手条件。

### 1.2 开工基线（在当前 HEAD `6127fc7` 上逐项实测，硬规矩 #111）

| 项 | 派单说的 | 实测 | 一致 |
|---|---|---|---|
| 分支 | `feature/plan-03-feedback-alert-crud-api` | 同 | ✓ |
| 工作树 | 干净 | 干净（只有未入库的 `task-8-brief.md`） | ✓ |
| 全量测试 | 1097 passed | **1097 passed** in 103.49 s | ✓ |
| 覆盖率四格 | 1147 / 0 / 336 / 0 / 100% | **1147 / 0 / 336 / 0 / 100%**（1096 passed, 1 skipped, 203.09 s） | ✓ |
| 表数 | 25 | **25** | ✓ |
| `_MODELS_PUBLIC_BASELINE` | 33（不动） | **33** | ✓ |
| 扫描面 | 54（pipeline 9 + db 11 + domain 17 + api 17） | **54**，逐目录同 | ✓ |
| 端点数 | 57 | `openapi()["paths"]` = **57**（operations 85） | ✓ |
| 四个指纹 | `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` / `E48E3AC82BB45BB7` | 逐字同，四个文件 CRLF 均为 **0** | ✓ |
| `backend/pe.db` | 不得存在 | **不存在** | ✓ |
| `backend/data/seed/` | 0 文件 | **0 文件** | ✓ |

### 1.3 P8-A1 的亲验：`_replay_cleanup` 开工时是 6 张，两种写法都能解析

AST 口径（探针 `t8_probes/p1_baseline.py` 第 [2][3] 段）实测清单：

```
['models.DerivedMetrics', 'models.StratificationResult', 'models.PercentileSnapshot',
 'WeeklyAdjustment', 'Prescription', 'Alert']      长度 = 6
```

**「两种写法在函数体里都能解析」已核实**（P8-A1 要求的那一格），机制是：

| 名字 | 顶层绑定 | 绑到 |
|---|---|---|
| `models.DerivedMetrics` 等三个 | `models` ← `from app.db import models` | **`app.db` 这个模块对象** |
| `WeeklyAdjustment` / `Prescription` | ← `from app.db.models.prescription import …` | 类对象 |
| `Alert` | ← `from app.db.models.feedback import Alert` | 类对象 |

函数体只有一个 `for model in (…): repo.delete_by_batch(session, model, batch_id)`，
故两种写法都归结成「取到一个带 `__table__` 的类」。
⚠️ 于是 **`WeeklyClassReport` 照 `Alert` 的形状写**（裸名，加进那条
`from app.db.models.feedback import …`），已落地。

**周日判据也当场核过**（派单点名这是本 Task 最容易错的一格）：

```
2025-09-13 Saturday   weekday()=5  isoweekday()=6
2025-09-14 Sunday     weekday()=6  isoweekday()=7     ← weekday() == 6 是周日 ✓
2025-09-15 Monday     weekday()=0  isoweekday()=1
```

`WeeklyClassReport` 实测 **12 列 / 5 个 `JsonText`**（`layer_distribution` /
`rpe_summary` / `checkin_rate_by_layer` / `progress_board` / `alert_summary`），与派单一致。

### 1.4 一个派单没提、而本 Task 必须先量的数：`training_days_of` 的吞吐

派单没给「按层分组的打卡完成率」的取数成本，而它决定了周报阶段能不能进整学期回放。
探针 `t8_probes/p2_timing.py`（500 人 / 与 `test_backfill.py` 逐字同的 `SeedConfig`，
写在 TEMP、显式设 `PE_DB_URL`，**没碰** `pe.db` 与 `data/seed/`）实测：

```
course_section 17 个 · enrollment 1000 行 · student 500 · prescription 498
training_days_of = 0.393 / 0.388 ms 每次（n=2）
→ 16 个周日 × 500 人（按 prescription_id 记忆化）≈ 3.1 s
→ 16 个周日 × 1000 (班, 生) 对（不记忆化）      ≈ 6.2 s
```

**结论**：加 `ClassCache` 的 `(prescription_id, 处方周次)` 记忆化（一个学生同时在
行政班与分层班的名册上，两处训练日是同一份），把成本压到 ~3.1 s。
最终实测（第 ⑧ 节）：`elapsed` **没有可辨的退化**。

---

## ② `app/domain/report.py`：`__all__`、值类型字段、覆盖率四格

### 2.1 公开面（运行时口径，探针 `p7_final.py` 第 [6] 段）

**`__all__` 长度 = 26**：10 个函数 + 1 个值类型 + 15 个常量。

```
函数（10）  abnormal_roster, alert_summary, checkin_rate_by_layer, daily_mean_rpe,
            layer_distribution, layer_flow, progress_board, rpe_summary,
            suggestion, week_mean_rpe
值类型（1） RpeWeek
常量（15）  CLASS_RPE_LOW_MAX, LAYERS, LEVELS, PCT_PRECISION, PROGRESS_BOARD_TOP_N,
            RATE_PRECISION, REASON_CHECKIN_GAP, REASON_RPE_HIGH, RPE_PRECISION,
            SCREEN_GAP_DAYS, SCREEN_RPE_MAX, SUGGESTION_HOLD, SUGGESTION_INCREASE,
            SUGGESTION_REDUCE, SUGGESTION_STEP_PCT
```

**全部值类型的字段**（`dataclasses.fields(...)` 运行时读，硬规矩 #89）：

| 值类型 | 字段（按声明序） | 逐字段回问「这个值从哪个入参来」（硬规矩 #110） |
|---|---|---|
| `RpeWeek` | `days`, `values` | `days` = 调用方注入的 7 个 ISO 串（domain 不 import `datetime`）；`values` = `{ISO 串: 那一天全部快评的 RPE}`，缺席的键与空列表同义 |

⚠️ **只有一个值类型**是有意的：其余九个函数的输出**就是**要落进 5 个 `JsonText` 列 /
回给前端的 JSON 载荷，故它们返回 `dict` / `list`（JSON 的 Python 影像），
不再套一层 dataclass → dict 的转换器（那会是一层需要自己 100% 覆盖的胶水）。

### 2.2 常量的值与它们的所有者

| 常量 | 值 | 所有者 / 出处 |
|---|---|---|
| `LAYERS` | `("red","yellow","green","insufficient_data")` | **派生自** `app.domain.stratify.Layer` 的声明序（不是第二份字面量） |
| `LEVELS` | `("red","yellow","green")` | **派生自** `app.domain.alerts.AlertLevel` |
| `SCREEN_GAP_DAYS` | `3` | spec §9.1 的 ASCII 图；**待体育专家确认** |
| `SCREEN_RPE_MAX` | `8` | 同上；**待体育专家确认** |
| `REASON_CHECKIN_GAP` / `REASON_RPE_HIGH` | `"checkin_gap"` / `"rpe_high"` | 载荷里的字面量（前端按它渲染图标） |
| `SUGGESTION_STEP_PCT` | `10` | 工程约定；**待体育专家确认** |
| `CLASS_RPE_LOW_MAX` | `5.0` | 同上 |
| `SUGGESTION_REDUCE` / `_INCREASE` / `_HOLD` | `"本周建议整体降量 10%"` / `"…加量 10%"` / `"维持当前强度"` | 前两个由 `SUGGESTION_STEP_PCT` **生成**、不手写第二遍 |
| `PROGRESS_BOARD_TOP_N` | `10` | spec §8.5 逐字「进步榜 Top10」 |
| `RPE_PRECISION` / `RATE_PRECISION` / `PCT_PRECISION` | `2` / `4` / `2` | `RATE_PRECISION` 与 `app.api.routers.feedback.RATE_PRECISION` 由一条测试钉成相等 |

### 2.3 覆盖率四格

```
Name                   Stmts   Miss Branch BrPart  Cover
app\domain\report.py     112      0     40      0   100%
```

`app/domain/` **合计**（第 ⑧ 节复述）：`1147 / 0 / 336 / 0 / 100%` →
**`1259 / 0 / 376 / 0 / 100%`**。⚠️ `Miss` 与 `BrPart` **仍是 0**、覆盖率**仍是 100%**
（spec §12 的硬要求）；stmts +112、branch +40，**恰为 `report.py` 一个文件的量**。

### 2.4 变异取证（Ruling 1 不要求，但 Task 2/3/4/5/7 的实现者都自己加了一轮）

探针 `t8_probes/p3_mutation.py`：**24 条变异，24 killed，0 存活，0 跳过**；
跑完从 TEMP 备份按字节写回，复核 `report.py` 42 992 字节逐字相等。

其中**两条是「先写测试 → 变异存活 → 补反例 → 再跑 killed」**的产物，两条都值得留档：

* **M13（`layer_flow` 的名单去掉 `sorted`）第一版存活**。原因：测试用的学生 id 是
  `9 / 3 / 6`，而 CPython 的 `set` 迭代序是**槽位序**（`hash(int) == int`，落槽 =
  `值 % 表长`），实测 `set({9:…,3:…,6:…}) | set(同)` 的迭代序恰好是 `[3, 6, 9]` = 升序。
  换成实测挑出的 `1 / 2 / 16`（并集迭代序 `[16, 1, 2]` ≠ `[1, 2, 16]`）后 killed。
  → **硬规矩 #107 的又一次兑现**：用谓词挑对象之前，先对一个已知反例验证谓词。
* **M23（`!=` → `is not`）第一版存活**。原因：测试里两个 `"yellow"` 是**字面量**，
  在 CPython 里是同一个驻留对象，故「按值比」与「按身份比」给出同一个答案；
  而生产路径上的标签是从 SQLite 读回来的**两个不同的 `str` 对象**。
  改成 `"".join(["yel","low"])` / `"".join(["yell","ow"])` 现拼的串后 killed
  （`is not` 会让**全班每个人都算成换过层**，而全链路不报错）。

其余 22 条覆盖：三个「两套并存」的阈值被合并（M2/M3/M4）、加权均值被换成日均值再平均（M5）、
`entered`/`left` 对调（M6）、空日画成 0（M7）、一层无人可测时 rate 给 0.0（M8）、
相对变化的分母去掉 `abs`（M9）、`old == 0` 不再算「判不了」→ 除零（M10）、
Top10 不截断 / 退步名单也截断（M11/M21）、建议的优先级反过来（M12）、
两个分布改成稀疏（M14/M15）、`delta` 不可测时给 0.0（M16）、`peak_rpe` 缺失补 0（M17）、
两个精度常量被改（M18/M24）、大屏名单不排序（M19）、进步榜的并列不打 tie-breaker（M20）、
「上周不存在」被当成「上周一个人都没有」（M22）、建议的低 RPE 边界从严格改成闭合（M1）。

---

## ③ `report_stage.py` 的公开面，与周报 5 个 `JsonText` 列各装什么

### 3.1 公开面（`__all__` 长度 = **12**）

```
常量/词表（3）  REPORT_WEEKDAY = 6, ALERT_STATUSES = ("pending","handled","ignored"),
                CLASS_RPE_HIGH_RULE = RuleId.YELLOW_CLASS_RPE_HIGH.value
值类型（3）     ClassCache（记忆化上下文）, ClassSnapshot（一个班一周的取数结果）,
                ReportSummary(generated, skipped, errors)
函数（6）       is_report_day, new_cache, labels_at, class_snapshot,
                aggregates_of, generate_weekly_reports
```

**签名的顶回**（第 ⑦ 节顶回 1）：`generate_weekly_reports(session, semester_id, batch_id,
week, *, as_of, now, exercises)` —— 比派单多 `now` 与 `exercises` 两个 keyword-only 形参。

**三层分工**（P8-A2 的落地，⚠️ 这是本 Task 最要紧的一个结构决定）：

| 层 | 职责 | 谁是唯一所有者 |
|---|---|---|
| `app/domain/report.py` | 九个聚合量（纯函数） | 判据与阈值 |
| `report_stage.class_snapshot` | 把一个班一周的库里的行读成 `ClassSnapshot` | **「怎么读一个班的一周」** |
| `report_stage.aggregates_of` | 把快照喂给那九个纯函数，得到**七个键** | **「怎么调那九个函数」** |
| `report_stage.generate_weekly_reports` | 取七个键里的六个落库 | 落库 |
| `api/routers/dashboard.py` | 取全部七个键回给前端 | HTTP |

⚠️ **大屏与周报共用中间那两层**，故「教师看到大屏写人均 6.9、同一周的周报写 7.1」
在结构上不可能发生。守卫是
`tests/api/test_dashboard.py::test_the_dashboard_and_the_stored_report_agree_on_the_same_sunday`
（同一个周日、同一个班，现算的大屏与存下来的周报的**六个共有键逐字相等**；
两侧不同源：一侧从 HTTP 响应体、一侧从库里那一行）。

### 3.2 五个 `JsonText` 列各装什么（**运行时实测的键集**，不是照代码抄）

| 列 | 顶层键 | 里面装什么 |
|---|---|---|
| `layer_distribution` | `by_layer` / `previous` / `flow` | `by_layer` = 四个标签的**稠密**计数（0 也在）；`previous` = 上周同一份分布，**上周不存在时是 `null`**；`flow` = `{has_previous, entered, left, appeared, disappeared}`，后四个是 `{标签: [学生 id 升序]}` |
| `rpe_summary` | `curve` / `previous_curve` / `mean` / `previous_mean` / `delta` | `curve` **恒 7 项**（学期周的那 7 天），没交快评的那天是 `null`，有数据的那天是 `{day, mean, submissions}`；`mean`/`previous_mean` **未 round**（它们是 `suggestion` 的判据输入），`delta` 与曲线上的 `mean` round 到 2 位 |
| `checkin_rate_by_layer` | 四个标签 | 每层 `{students, measured, rate}`；`rate` 可空 = 「这一层一个可测的人都没有」（**不是** 0.0），round 到 4 位 |
| `progress_board` | `top_n` / `top` / `regressed` / `unchanged` / `unmeasured` | `top` 截断到 10、`regressed` **不截断**；每项 `{student_id, change_pct}`；变化恰为 0 的进 `unchanged`（两个榜都不进）；分数缺失或上次是 0 分的进 `unmeasured` |
| `alert_summary` | 三个级别 | 每级 `{pending, handled, ignored}` —— **3 × 3 双稠密**，9 个格子一个不缺 |

第 6 项 `suggestion` 落在 **`Text`** 列（自由文本，不是 JSON），三档之一。
⚠️ **`abnormal_roster` 不落库**：它是 §9.1 大屏的第 ④ 块（一个实时筛选器），
不是 spec §4.7 那 6 项里的一项，而 `weekly_class_report` 只有 5 个 JSON 列 + 1 个 Text 列、
没有它的位置。它由 `aggregates_of` 算出来、只出现在大屏响应里。
（`report_stage._JSON_COLUMNS` 与「表上 5 个 `JsonText` 列」由
`test_the_json_column_list_matches_the_five_jsontext_columns_of_the_table` 按集合对账。）

### 3.3 三个窗口口径（硬规矩 #113：两处要回答的是不是同一个问题）

| 量 | 窗口 | 它回答的问题 |
|---|---|---|
| 分层标签（本周 / 上周） | `computed_on <= watermark` / `<= 上周末` | 这一周结束时每人在哪一层 / 环比的基准 |
| 人均 RPE 曲线的**横轴** | 学期第 N 周的**全 7 天** | 曲线的 x 轴（水位线之后是 `null`，横轴不缩短） |
| 打卡 / 小测 / 预警 | `[week_start, watermark]` | 本周发生了什么 |
| **完成率的分母** | 处方训练日 **∩ 学期第 N 周** ∩ `<= watermark` | 「这个班**本周**按层分组练得怎么样」 |
| **连续未打卡天数的窗口** | 本处方周 + 上一处方周，`<= watermark` | 「这个学生**失联多久了**」 |

⚠️ 后两行**刻意不同**，而理由是 #113 的两侧各一条：

* 完成率的分母与 `alert_stage._student_signals` **不同**（那一处是整个处方周）——
  两个问题不同；共用一个窗口的话，一个处方周跨两个学期周的学生会在两份周报里
  各被算一次完整分母，两周的完成率都偏低，且全程不报错。
* 连续未打卡天数与 `alert_stage` **逐字相同**——同一个问题；收窄到学期周的话，
  一个上周就开始失联的学生本周只错过 2 天 → 大屏的「连续 3 天」筛不到他 →
  而预警那一条（阈值 2 天）**已经**给他开了工单。同一个学生在工单里在、在大屏上不在。

⚠️ 而**分子的四个条件**（`completed` ∧ `not late` ∧ `not is_rest_day` ∧
`submitted_at.date() == log_date`）与「有没有报过」那一份，一律 `import`
`alert_stage._counted_checkin_days` / `_reported_checkin_days`，**不写第二份**
（前者已经有一条测试把它与 `GET …/completion-rate` 端点钉成逐字相等）。
`training_days_of` 同样只从那一个住址 import（AST 口径实测全仓**定义份数 = 1**，P8-A3）。

---

## ④ 周日判据：落地位置与它的边界测试

### 4.1 落地位置（**拆成两半**，简报 Task 8「决定」第 3 条）

| 谁 | 持有什么 |
|---|---|
| `report_stage.REPORT_WEEKDAY = 6` | 「6 是周日」这个数（**有名字的常量**，不是裸的 6） |
| `report_stage.is_report_day(as_of)` | 判据本身：`as_of.weekday() == REPORT_WEEKDAY` |
| `daily.run_daily` | **调用点**：`if is_report_day(as_of):` 里面再算 `report_week = semester_week_of(...)`，`if report_week is not None:` 才调 `generate_weekly_reports` |
| `generate_weekly_reports` | **无条件**为 `(semester_id, week)` 生成一遍（它不判今天星期几） |

**为什么判据不住在生成器里**：把判据放进生成器的话，「重放一个历史日期」与
「那一天是不是周日」就绑死了；一个手工补生成上周周报的入口（Plan 04 的教师端很可能要）
会被生成器自己挡掉，而调用方看不出为什么。

**为什么是两个条件**：`is_report_day` 刻意**不知道**学期周次。一个开学日之前的周日，
`is_report_day` 仍然说「是周日」，挡掉那一次生成的是 `semester_week_of(...) is None`
（那一天没有「本学期第几周」可言，而 `weekly_class_report.week` 是 NOT NULL、
且是幂等键 `uq_weekly_class_report_section_semester_week` 的一列）。
**两件事不互相掩盖**，故两个判据都要在，且各有一条测试。

**顺带落地的一格**：`run_daily` 里内联的 `now=dt.datetime.now()` 被提成一个局部变量
`now`，喂给 `evaluate_alerts` 与 `generate_weekly_reports` **两个**阶段。
理由是 `alert_stage` 自己 docstring 里那条纪律的延伸（「本阶段的三个时刻列必须是
同一个时刻」）：周报的 `generated_at` 也必须落在同一个时刻上，否则同一批里
「预警触发」与「周报生成」的先后顺序会随两次 `now()` 的调用点漂，
而教师端按时刻排序时一份周报会排在它所汇总的那些预警**之前**。
⚠️ `finished_at` 刻意**不**用这个 `now`（它是「整批跑完」的时刻，与本批的业务时刻是两件事）。

### 4.2 边界测试（周六 / 周日 / 周一三格，派单逐字要求）

三条都在 `tests/pipeline/test_report_stage.py`，日期一律**字面写死**、
且都真的跑一遍 `daily.run_daily`（不是只调 `is_report_day`）：

| 测试名 | 日期字面 | 星期 | 期望 |
|---|---|---|---|
| `test_a_saturday_does_not_generate_a_report` | **2025-09-13** | 周六（`weekday()==5`） | `weekly_class_report` **0 行** |
| `test_a_sunday_generates_a_report` | **2025-09-14** | 周日（`weekday()==6`） | **1 行**，`week == 2`，`batch_id == 那一批的 run.id` |
| `test_a_monday_does_not_generate_a_report` | **2025-09-15** | 周一（`weekday()==0`） | **0 行** |

外加四条把这一格钉死的：

* `test_the_report_weekday_constant_is_six_and_six_is_sunday` —— `REPORT_WEEKDAY == 6`
  且 `SUNDAY.weekday() == REPORT_WEEKDAY`，**并反证** `SATURDAY.isoweekday() == 6`
  而 `SATURDAY.weekday() != REPORT_WEEKDAY`（即：写成 `isoweekday() == 6` 会命中周六）。
* `test_is_report_day_over_one_whole_real_week` —— 2025-09-08..14 七天逐个过，
  先断言 `strftime("%a")` 是 `Mon..Sun`（钉住这七天真的是那一周），
  再断言布尔列表 `[F,F,F,F,F,F,True]`。⚠️ 只有「一个是 True」那种断言挡不住
  「判据挪到了周六」，逐个列出七天可以。
* `test_a_sunday_before_the_semester_starts_generates_nothing` —— **2025-08-31**
  （开学前那个周日）：先断言 `is_report_day` 为 **True**、`semester_week_of` 为 **None**，
  再断言跑完 `run_daily` 后 0 行。即「挡它的不是星期几」。
* `tests/pipeline/test_daily.py::test_a_non_sunday_never_calls_the_report_stage` ——
  判据是 **spy 一次都没被调用**，而不是「表是空的」（后者在「调用了但名册全为空 →
  `skipped`」时也是空表，两档同形）。

阶段接线另有 `test_the_report_stage_runs_last_and_shares_one_instant_with_the_alert_stage`：
两个 spy 记下调用先后 → `calls == ["alert", "report"]`；
且 `weekly_class_report.generated_at` 的**集合**等于 `evaluate_alerts` 那个 spy
**现场记下来**的 `now`（期望侧不是 `generated_at` 自己，故两侧不同源）。

---

## ⑤ `_replay_cleanup` 从 6 张扩到 7 张：证据与钉住它的测试

### 5.1 AST 口径的前后对照（探针 `p1_baseline.py` / `p7_final.py`）

| # | 开工时（`6127fc7`，6 张） | 结案时（7 张） |
|---|---|---|
| 1 | `models.DerivedMetrics` | `models.DerivedMetrics` |
| 2 | `models.StratificationResult` | `models.StratificationResult` |
| 3 | `models.PercentileSnapshot` | `models.PercentileSnapshot` |
| 4 | `WeeklyAdjustment` | `WeeklyAdjustment` |
| 5 | `Prescription` | `Prescription` |
| 6 | `Alert` | `Alert` |
| 7 | — | **`WeeklyClassReport`** ← 本 Task 加的 |

⚠️ **照 `Alert` 的形状写**（裸名 + 加进 `from app.db.models.feedback import …`），
而**没有**「统一」成一种写法：前三个带 `models.` 前缀是因为那三张**在**
`app.db.models` 的公有导入面上（Ruling 97 的 33 个名字里），后四个刻意不在，
只能走子模块路径 import 进来再用裸名引用。**两种写法的区别是一个事实、不是风格**，
这一段逐字写进了元组里 `WeeklyClassReport` 上方的注释（下一个想「整理」的人会先读到它）。

**位置不承重**：全库没有任何一张表的外键指向 `weekly_class_report`，
而它自己的三个外键指向 `course_section` / `semester` / `daily_sync_run`
——三张都不在清单里。故排在末尾只是书写序（与 `Alert` 同一条理由）。

⚠️ **`notification` 仍不进清单**（派单 P8-A1 的后半）：它不带 `batch_id`，
而它的 `alert_id` 与 `prescription_id` 都带 `ondelete="SET NULL"`，
故删 `alert` / `prescription` 不会让通知行炸 FK。这一点由 Task 7 的
`test_replay_cleanup_covers_alert_and_leaves_the_notification_alone` 继续看着（本 Task 未改它，仍绿）。

### 5.2 钉住清单长度与成员的那条测试

**`tests/pipeline/test_report_stage.py::test_the_replay_cleanup_list_is_pinned_to_seven_tables`**

* 判据是 **AST 口径**（`ast.parse(daily.py)` → 找 `_replay_cleanup` 的 `For` →
  它的 `iter` 是 `Tuple` → `ast.unparse` 每个元素），**绝不用正则数源码**（硬规矩 #89）：
  那个元组的元素既有 `models.X` 也有裸名 `X`，还夹着注释，正则要么数错、要么把注释里的名字也数进来。
* 期望侧是测试文件里**字面写死**的 `REPLAY_CLEANUP_SEVEN`（7 个名字，按书写序），
  逐字比对 + `len(...) == 7`。
* 形状照 Task 7 的 `test_replay_cleanup_still_does_not_cover_class_session`
  （那一条钉的是「**不得**进清单」的那一张），派单 P8-A1 逐字要求照它办。

配套的三条：

* `test_the_two_spelling_styles_in_the_list_both_resolve` —— 把 P8-A1 要求核实的
  「两种写法都能解析」变成可执行的：`daily.models is app.db.models` 模块对象，
  四个裸名各自的 `__tablename__` 是 `weekly_adjustment` / `prescription` / `alert` /
  `weekly_class_report`（期望侧是 SQLAlchemy 的表元数据，不是源码文本）。
* `test_replay_cleanup_covers_weekly_class_report` —— **行为面**：先断言那一行
  `batch_id == 本批`（否则删掉它证明不了什么），跑 `_replay_cleanup` 后
  `count(WeeklyClassReport) == 0` 且 `session.get(..., report_id) is None`。
* `test_replaying_a_sunday_keeps_exactly_one_report` —— 整条管道上的可见后果：
  同一个周日跑两遍 `run_daily` → 仍是一行。
  ⚠️ 本条**刻意不断言 `id` 变了**（前一版这么写、当场红）：SQLite 的 rowid 分配是
  `max(rowid) + 1`，删掉唯一那一行之后 `max` 回到 0，重新插入拿到的仍是 `1`
  ——「删了再插」与「就地更新」在 `id` 上**同形**，故 `id` 不是这一档的判据。
  这一格如实写进了那条测试的 docstring。

### 5.3 漏掉它的失效形态（写进了 `daily.py` 的 docstring 与 `report_stage` 的 docstring）

**不是「翻倍」**（`uq_weekly_class_report_section_semester_week` 挡着，`repo.upsert`
会走更新分支），而是更隐蔽的一格：那一行会**静默沿用上一轮的 `batch_id`**，
于是下一次重放按新的 `batch_id` 删时**删不到它**——它从此永远停在旧批次上，
而 `daily_sync_run` 的计数看起来全都正常。

---

## ⑥ P8-A5 的教师端变体

### 6.1 路径 / 身份头 / 响应

| 项 | 值 |
|---|---|
| 路径 | **`GET /api/teacher/students/{student_id}/weekly-sheet?as_of=`** |
| 身份头 | **`X-Teacher-Staff-No`**（+ `dependencies=[Security(TEACHER_STAFF_NO_SCHEME)]`） |
| 闸门 | `deps.require_teacher`（在册）→ **`deps.require_teaches_student`**（任教关系） |
| 响应模型 | **与学生侧同一个** `WeeklySheetRead`（两个端点在 `/openapi.json` 里指向同一个 schema，实测 `$ref` 逐字相等） |
| 响应体 | **与学生侧逐字相同**（守卫 `test_the_teacher_and_the_student_variants_return_the_same_body`） |
| 两档 404 | `no_active_prescription` / `outside_microcycle`，**码与文案逐字同学生侧** |

### 6.2 任教关系校验的那条链

```
X-Teacher-Staff-No
  → teacher.staff_no  ⟶  teacher.id                    （deps._teacher_id_of）
  → course_section.teacher_id == teacher.id
  → enrollment.course_section_id == course_section.id
  → enrollment.student_id == student_id
  ∧ enrollment.semester_id == course_section.semester_id == 「as_of 所属的那个学期」
```

「`as_of` 所属的那个学期」由 `app.pipeline.percentile_stage.current_semester_of`
解析（**它是「哪一个是本学年」的唯一所有者**：优先 `is_current`、退化到「包含 `as_of` 的那个」），
闸门自己不查一遍 `semester` 表、也不自己猜。

⚠️⚠️ **`semester_id` 是必填的第四个入参，而它是承重的**——这是本 Task **顶回自己的一版草稿**
（第 ⑦ 节顶回 3）：第一版没有它，判据于是退化成「他**曾经**教过这个学生」，
被 `test_teaching_last_semester_does_not_grant_access_this_semester` 当场抓到
（一位上学期教过某人的教师，这学期仍读得到那个人**本学期**的训练单，
而那个学生已经不在他的班上了）。

⚠️ 「不存在」与「不是你的」**一律同报 403**（口径同 `require_scope`：区分两者等于把
在册名单告诉调用方）。⚠️ 代价如实记录：一个把 id 打错的前端会看到 403 而不是 404，
于是它以为自己没有权限、去查登录态；这一档由 `detail` 里的原话兜住
（它明写「或这个学生不存在」）。

### 6.3 连带：班级那一侧也收窄了

`require_teaches_section`（`teacher.id` → `course_section.teacher_id`，一跳）挂在
`GET /api/dashboard/class/{id}` 与 `GET /api/dashboard/weekly-class-report/{id}` 上。

⚠️ 于是 `deps.require_teacher` docstring 里那句「原型没有教师 ↔ 班级 ↔ 学生的授权模型」
**已经不成立**，本 Task 把它改写成如实的：模型建出来了，但**只挂在读的一侧**；
三个**写入**端点（`POST …/overrides` / `POST …/regenerate` / `POST …/alerts/{id}/handle`）
今天仍只过 `require_teacher`，故任何在册教师可以覆盖任何学生的处方——
如实记录，已登记为关切（收窄它们是一次一行的改动，但那会改掉 Plan 04 教师端的可点范围，
故不在本 Task 里顺手做）。`require_scope` 的 docstring 里那句「教师端的读写按设计是跨学生的」
也一并改写。

### 6.4 security 清单：12 项 → **17 项**

`tests/api/test_prescription_api.py::test_the_identity_headers_are_registered_as_openapi_security_schemes`
的 `expected` 清单加了 **5** 行（那条守卫的 docstring 逐字写着「Task 7/8/9 每加一个带身份的
特例端点都要回来加一行——**这是有意的**」，故按其设计登记；它的 docstring 里那句
「Task 7 起是 12 项」也一并改成「Task 8 起是 **17** 项」）。

新增的 5 行（实测自 `/openapi.json`，探针 `p4_endpoints.py`）：

```
("/api/dashboard/class/{course_section_id}", "get"):                   "X-Teacher-Staff-No"
("/api/dashboard/weekly-class-report/{course_section_id}", "get"):     "X-Teacher-Staff-No"
("/api/teacher/students/{student_id}/weekly-sheet", "get"):            "X-Teacher-Staff-No"
("/api/students/{student_id}/home", "get"):                            "X-Student-Id"
("/api/notifications/{notification_id}/read", "post"):                 "X-Student-Id"
```

⚠️ 第 ③ 拍（「除清单之外无 `security`」的全仓级断言）的下界是 `>= 70`，
实测**不带** security 的 `/api/` 操作数 = **73**，故没有空转、也没有被新端点顶穿。
`components.securitySchemes` 仍**恰好两格**，spec 顶层仍**没有** `security`。

### 6.5 大屏 / 首页聚合端点的路径清单（本 Task 新增的 5 个，一行一个）

```
GET  /api/dashboard/class/{course_section_id}
GET  /api/dashboard/weekly-class-report/{course_section_id}
GET  /api/students/{student_id}/home
GET  /api/teacher/students/{student_id}/weekly-sheet
POST /api/notifications/{notification_id}/read
```

---

## ⑦ 待清扫 / 关切 / 没按派单做的地方 / 顶回控制者的地方

### 7.1 顶回控制者的地方（**4 处**）

**顶回 1（Important）：`generate_weekly_reports` 的签名跑不起来，缺 `now` 与 `exercises`。**
派单 Interfaces 逐字写的是 `(session, semester_id, batch_id, week, *, as_of) -> ReportSummary`。
而 ① `weekly_class_report.generated_at` 是 `DateTime NOT NULL` **且无缺省**
（本仓全部表的统一约定：时钟由调用方注入，守卫是
`test_the_plan03_tables_inject_the_clock_and_never_default_it`）；
② `training_days_of` 要 `exercises`，而 `prescription_stage` 的既有纪律是
「三份参考数据一律由调用方注入」，故 `report_stage` 不自己调 `refdata_prescription.exercises()` 单例。
**这与 Task 7 顶回 `evaluate_alerts` 签名是同一件事、同一条理由**（控制者当时采纳了）。
落地：`*, as_of, now, exercises`，并在 docstring 里逐字交代了「为什么必须与预警阶段同一个 `now`」。

**顶回 2（Important）：`ReportSummary` 加第三格 `errors`。**
派单只给了 `generated` / `skipped`。而周报阶段有两层异常捕获（按班 + 按人），
没有第三格的话「取数失败」就只有一条日志、报表上看不见——
而 `AlertReport` 与 `PrescriptionReport` 都有 `errors`（Task 6/7 的先例）。
⚠️ 而 `skipped` 的口径派单**没给**，本 Task 定成「**名册为空**的教学班」，
并逐字写明它**不是**「判不了」的垃圾桶（两格分开，否则「一个班没学生」与
「一个班的数据坏了」在计数上同形）。守卫 `test_report_summary_has_exactly_three_fields`
+ `test_a_section_without_a_roster_is_skipped_and_gets_no_row`。

**顶回 3（Important，方向是「加严」而不是「放松」）：P8-A5 那条链必须带学期。**
派单写的是「教师只能看自己教的班的学生；`enrollment` 表 + `course_section.teacher_id` 是那条链」，
**没有**说要按学期收窄。而不收窄的话，判据是「他**曾经**教过这个学生」，
于是一位上学期教过某人的教师这学期仍读得到那个人**本学期**的训练单
——那正是这道闸门要挡的形状。故 `require_teaches_student` 的第四个入参 `semester_id` 是必填的，
由调用方经 `current_semester_of(session, as_of)` 解析。
⚠️ 这一格是**被自己的测试抓到的**（第一版没有它，`test_teaching_last_semester_…` 当场绿不了），
不是先想到的；如实记录。

**顶回 4（Minor，方向是「支持派单的结论、但理由要换一条」）：P8-A6 不加 `screen:` 段是对的，
而成本比派单说的更高。**
派单给的两条理由是「大屏的阈值没有 spec 出处」与「要按 P9-A3 六步程序改指纹」。
实测还有**第三条**、而且是硬性的一条：`app.refdata_alerts.load_alert_rules` 的
docstring 逐字写着校验顺序是「**顶层键集** → `version` → `rules` 的键集 → 逐条规则」，
即顶层键集是**恰好相等**的判据（与它对 `rules:` 键集「多一个、少一个都响亮失败」是同一条纪律）。
故加一个 `screen:` 顶层段**当场就会让加载器响亮失败**，必须同步改 Task 6 已结案的
那个顶层键集常量与它的守卫测试——那是在「改指纹」之外**再**动一个已结案的守卫。
**处置照派单办**（不加 `screen:` 段，四个指纹逐字不变），
大屏与周报要用的阈值/文案一律做成 `app/domain/report.py` 的模块级常量并注明
「**待体育专家确认**」，与 Plan 02 处理 `Intensity.rpe` 的方式一致。
⚠️ 若控制者认为某个量真的要被专家调，请连同「顶层键集守卫要不要放行 `screen:`」一起裁定。

### 7.2 没按派单做的地方（**5 处**）

1. **`app/api/schemas/dashboard.py` 是派单 Create 清单之外的新文件**（16 个响应模型）。
   理由：五个新端点若不带 `response_model`，它们在 `/openapi.json` 里就只有一个裸的 `{}`，
   而用户 2026-09-28 的原话是「要确保后端和前端能够对接的上」（P4-A5 为同一件事给两个
   身份请求头补过 securityScheme）。⚠️ 那 16 个模型**不进**「14 + 9 × 3 = 41」那条算式
   （它数的是 23 个资源），守卫 `test_the_dashboard_schemas_are_not_part_of_the_crud_matrix`
   把这句话变成了可执行的；`schemas/__init__.py` 的布局表也加了一行。
2. **多改了三个派单 Modify 清单之外的文件**：
   `app/api/deps.py`（两道新闸门；它是「身份与作用域闸门」的既有住址，
   放在 router 里会让下一个教师端点再写一份）、
   `app/api/routers/prescription.py`（把 `weekly_sheet` 的函数体抽成
   `_weekly_sheet_response`，两个端点共用一个所有者）、
   `app/api/schemas/__init__.py`（布局表加一行）。
3. **`_replay_cleanup` 的 AST 断言放在 `test_report_stage.py`，不在 `test_daily.py`。**
   派单说 `test_daily.py` 要改「阶段序列与 `_replay_cleanup` 的断言」。
   阶段序列那一部分照办了（`test_daily.py` 加了 2 条接线测试）；
   而 `_replay_cleanup` 的清单断言放在 `test_report_stage.py`，
   **与 Task 7 把 `Alert` 那一条放在 `test_alert_stage.py` 同构**（谁加的表谁钉它）。
   `test_daily.py` 的模块 docstring 已改写，逐字指明了三处各自的住址。
4. **`test_daily.py` 的 `PIPELINE_TABLES`（canonical sha256 那 11 张）刻意没加
   `weekly_class_report`。** 那条测试跑在 `D = "2025-09-15"`（**周一**），
   故周报表在两次运行里都是空的，加进去是一条**空转**的守卫；
   而它的 docstring 已经印着一个过期的字面哈希（P7-A6 记的账），
   再动它只会让散文更过期。周报的幂等由 `test_replaying_a_sunday_keeps_exactly_one_report`
   + `test_replay_cleanup_covers_weekly_class_report` 直接钉，两条都比「对一张空表求哈希」强。
5. **`generate_weekly_reports` 里删掉了一段自己第一版写的、不可达的校验。**
   第一版在 `_require_batch_in_semester` 之后又写了一次
   `if session.get(Semester, semester_id) is None: raise ValueError(...)`。
   实测那一道**不可达**：`_require_batch_in_semester` 比对的正是
   `daily_sync_run.semester_id`，而那一列是 NOT NULL 外键，故「批次与学期是同一次运行」
   成立时那个学期行必然在。删掉它，并把「学期 id 打错了」那一档实际报的话
   （批次不匹配那句）如实写进 docstring 与
   `test_an_unknown_semester_fails_loudly_not_silently`。
   ⚠️ 可达的那一道留在 `class_snapshot` 里（大屏可以直接用一个打错的 `semester_id` 调它）。

### 7.3 待清扫（**6 条**）

1. **`_stratification_payload` 是 `input_snapshot_of` 的逆运算，而正向那一份住在
   `app/pipeline/run_stratify.py`。** 逆向今天只有一个消费者（学生首页），故放在
   `app/api/routers/dashboard.py`；等出现第二个消费者时应当提到 `run_stratify.py`
   与正向那一份并排住。⚠️ 漂移今天**不会**静默：正向的 28 个键由
   `test_input_snapshot_gains_the_raw_bmi_and_the_p10_line` 逐字钉死，
   而 `test_the_whole_screen_survives_a_real_pipeline_run` 真的跑一遍 `run_daily`
   再打首页（改一个键名 → 那条红）。
2. **两档 404 的形状在 `/openapi.json` 里看不见**（教师端与学生端两个 weekly-sheet 都是）：
   `response_model=WeeklySheetRead` + 「返回 `Response` 实例时 FastAPI 跳过校验」这条既有口径
   让 200 有 schema、404 没有。前端只能按 `app.api.errors` 的统一形状与两个 `code` 分支。
3. **`daily_sync_run` 没有 `report_count` 列**，故「本批生成了几份周报」不落库，
   载体只有 `report_stage` 那一条 `info` 日志与 `weekly_class_report` 表本身。
   ⚠️ 本 Task **刻意没加**那一列（加一列等于改 25 张表的 DDL，而本仓不做迁移）。
   CLI 因此只打印「本日生成 / 本日不生成」，不打印份数。
4. **教师侧的「通知已读」今天没有端点**：`POST /api/notifications/{id}/read` 只认
   `recipient_kind = "student"`，而教师确实会收到班级黄牌的通知（`alert_stage._notify`）。
   spec §9.1 的大屏版面里没有消息中心，故留给 Plan 04 决定要不要做。
   ⚠️ 做它的正确形状是**另一条路径**（教师身份 + `recipient_kind = "teacher"`），
   不是把现有端点改成「学生或教师任一即可」（那要判两条规则、两个失败码，
   理由逐字见 `app/api/routers/prescription.py` 的模块 docstring）。
5. **`mini_test.normalized_score` 仍然只有 `demo_data` 一个写入方**（演示口径的近似值），
   而进步榜读的就是它。故在生产路径上（三源由适配器流入、教师从 `/normalized` 现算而不回写）
   进步榜会读到 `NULL` → 全员 `unmeasured`。⚠️ 这一格是 Task 5 登记的关切的**下游后果**，
   本 Task 把它逐字复述进了 `app/domain/report.py` 与 `report_stage.py` 的模块 docstring。
   要消除它就得让 `/normalized` 回写，而那会让一个 `GET` 有副作用（本仓不接受）。
6. **三个写入端点（教师覆盖 / 手动重生成 / 预警处置）仍只过 `require_teacher`**（在册），
   不过任教关系闸门。见 7.1 顶回 3 与 `deps.require_teacher` 的 docstring。

### 7.4 关切（**4 条**，都是「写下能力就写明守不住什么」，硬规矩 #39）

1. **等权均值的代价**：`checkin_rate_by_layer` 是「一层里可测的那些人的完成率**均值**」
   （每人等权），不是「全班完成天数 / 全班应打卡天数」。前者只要一个已经算好的比率，
   后者要给每个学生先装配一遍处方训练包。代价是一个每周练 2 天的绿层学生与一个每周练 5 天的
   红层学生在均值里同样重；`students` 与 `measured` 两格因此都在载荷里。
2. **`appeared` / `disappeared` 与 `entered` / `left` 不能单独用来核对人数恒等式**：
   「本周人数 = 上周人数 − left + entered」要连后两档一起算，而本模块**不替前端做这一步**
   （它会是一个今天没有消费者的新聚合量）。
3. **一个天天迟交的学生**：完成率永远不达标（`late` 不计入完成）、
   而「连续未打卡天数」永远是 0（`_reported` 只看有没有报过）。
   两个口径对他给出两个方向相反的结论。⚠️ 这一格是 Task 7 登记的关切的**继承**，
   本 Task 因为同时用了两个口径而让它在同一屏上可见（大屏的异常名单与按层完成率）。
4. **`enrollment` 在生产路径上没有写入方**：故「教师能不能看这个学生」取决于有没有人把
   选课行录进来，漏录的表现是教师端 403 而不是一条看得见的提示。
   （`alert_stage` 的模块 docstring 记的是同一件事的另一面。）

---

## ⑧ 最终验收

### 8.1 测试与覆盖率

| 项 | 基线（`6127fc7`） | 结案（HEAD） | 备注 |
|---|---|---|---|
| 全量（不带 `--cov`） | **1097 passed** / 103.49 s | **1225 passed** / 138.52 s | **+128 条** |
| 全量（带 `--cov=app.domain --cov-branch`） | 1096 passed, 1 skipped | **1224 passed, 1 skipped** / 253.25 s | 那 1 条 skip 是 `elapsed < 90` 在 trace 钩子下的既有处置 |
| `app/domain/` **stmts** | 1147 | **1259** | +112（恰为 `report.py` 一个文件） |
| `app/domain/` **Miss** | 0 | **0** | ✓ 必须仍是 0 |
| `app/domain/` **branch** | 336 | **376** | +40（同上） |
| `app/domain/` **BrPart** | 0 | **0** | ✓ 必须仍是 0 |
| `app/domain/` **Cover** | 100% | **100%** | ✓ spec §12 的硬要求 |

新增的 128 条分布：`tests/domain/test_report.py` **55** ·
`tests/pipeline/test_report_stage.py` **35** · `tests/pipeline/test_daily.py` **+2** ·
`tests/api/test_dashboard.py` **36**。既有 1097 条**一条都没退步**。

### 8.2 结构计数

| 项 | 基线 | 结案 | 说明 |
|---|---|---|---|
| 表数 | 25 | **25** | 本 Task 不建表 ✓ |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33** | 不动 ✓ |
| 扫描面 | 54（pipeline 9 + db 11 + domain 17 + api 17） | **58**（pipeline **10** + db 11 + domain **18** + api **19**） | +`report_stage.py` / +`report.py` / +`routers/dashboard.py` + `schemas/dashboard.py` |
| 端点数 `openapi()["paths"]` | 57 | **62** | +5 |
| operations | 85 | **90** | +5 |
| `_replay_cleanup` 清单 | 6 张 | **7 张** | +`WeeklyClassReport` |
| `training_days_of` 定义份数（AST） | 1 | **1** | P8-A3 ✓ |
| 带 security 的特例端点 | 12 | **17** | +5 |
| 不带 security 的 `/api/` 操作数 | ≥ 70（守卫下界） | **73** | 未空转、未顶穿 |

### 8.3 禁区与指纹

| 项 | 结果 |
|---|---|
| `D2C8E539E2FA0029`（`national_standard_2014.csv`） | **逐字不变** ✓ |
| `5394B37F01DAC9AC`（`exercises.yaml`） | **逐字不变** ✓ |
| `822CB86A5E998301`（`exercise_equivalence.yaml`） | **逐字不变** ✓ |
| `E48E3AC82BB45BB7`（`alert_rules.yaml`） | **逐字不变** ✓（P8-A6：不加 `screen:` 段） |
| 四个文件的 CRLF 计数 | 全 **0** ✓ |
| `git diff 6127fc7 HEAD -- backend/data` | **空** ✓ |
| `backend/pe.db` | **不存在** ✓ |
| `backend/data/seed/` | **0 文件** ✓ |

⚠️ 全程未跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`
的 CLI；探针要数据集时一律在 python 里 `build_dataset(cfg)` + `write_csv(..., TEMP)`，
数据库一律 TEMP 下的独立文件或 `sqlite://`，且显式设 `PE_DB_URL`
（`app/config.py` 的 `DEFAULT_DB_URL` 指向禁区 `pe.db`）。
控制者那个跑在 `127.0.0.1:8000` 的 uvicorn 未被触碰（本 Task 一个服务都没起）。

### 8.4 性能哨兵（`test_backfill_500_students_under_90_seconds`）

取证手段逐字照 Plan 03 Task 5 的那一条：**把阈值临时改成必然红的 `1`、从 pytest 的
assert 输出里读回真值、跑完从内存里的原字节写回**（不用 `git checkout`，硬规矩 #46）；
探针 `t8_probes/p6_backfill_elapsed.py`，还原后复核 `test_backfill.py` **32 588 字节逐字相等**、
阈值那一行仍是 `assert elapsed < 90, elapsed`。测量条件同那一条：
全量 `python -m pytest -q`、**不带** `--cov`、本地 SQLite 文件、`elapsed` 只夹 `run_backfill`。

| 口径 | 值 |
|---|---|
| 基线（Plan 03 Task 5 亲跑 n=2） | 47.33 / 47.96 s，均值 47.65 s |
| **本 Task 之后（n=2）** | **43.96 / 48.37 s，均值 46.16 s** |
| 差 | **−1.48 s = −3.1%**（组内极差 4.41 s，故**测不出**周报阶段那 ~3.1 s 的成本） |
| 对阈值 90 的余量（按最坏值 48.37 s） | **1.86×**（基线 1.88×） |

⚠️ 如实记录：1.86× 仍**不满足**硬规矩 #42 的 2× 线，而那条线是为「性能契约」定的，
本条自 Plan 03 Ruling 12 起已经**不是**契约（它是「数量级哨兵」）——
结论「没有慢出一个数量级」在 1.86× 余量下依然稳定，因为要推翻它需要一次 1.86× 的退化，
而那种退化（Plan 02 Task 7 的 115.08 s）正是它要抓的对象。**本 Task 没有让它变薄**
（1.86× 与 1.88× 之差在 n=2 的组内极差 4.41 s 之内）。
⚠️ 记忆化的收益是**结构性**的、不被这条哨兵看着：探针实测一次 `training_days_of`
约 0.39 ms，故记忆化把整学期回放的装配次数从 16 000 压到 8 000（省约 3.1 s）；
守卫是 `test_the_cache_memoises_the_training_day_assembly`（判据是**装配次数**，不是耗时）
+ 一条反证 `test_a_fresh_cache_does_not_share_the_memo`（换一个新的 `ClassCache` 就会重新装配，
故上面那条的绿不是「spy 根本没被调」）。

### 8.5 架构守卫

`tests/architecture` 全绿（8 条）。⚠️ 其中
`test_api_layer_dependency_direction_is_one_way` 的 allow-list 里
`app.refdata_alerts` **已在列**（Task 1 就为「后面 8 个 Task 不再动本文件」预留了它），
故 `dashboard.py` 现读阈值线没有让守卫变红、也没有改守卫。
`test_production_layers_never_import_app_seed` 的空转下界是 `>= 18`，实测扫描面 58，未触。
`tests/architecture/test_domain_purity.py` 的三条对 `report.py` 全绿
（它只 import `collections.abc` / `dataclasses` / `app.domain.alerts` / `app.domain.stratify`，
**不 import `datetime`**，日期一律由调用方注入 ISO 串）。

### 8.6 commit

| sha | 一句话 |
|---|---|
| **`6b5decc`** | `feat(domain)` ①：`app/domain/report.py` —— 周报与大屏共享的九个聚合量（26 个公开名、112 stmts / 40 branch / 100%、24 条变异全 killed） |
| **`e593532`** | `feat(pipeline)` ②：Report 阶段接进 `daily.py`（周日判据 + 同一个 `now`）+ `_replay_cleanup` 六张 → 七张 |
| **`415db83`** | `feat(api)` ③：大屏/首页聚合读接口 + P8-A5 的教师端训练单变体 + 通知已读（security 清单 12 → 17） |
| 收尾 | `docs(sdd)` ④：本报告 + 派单 + 7 个探针脚本 |

⚠️ **未 push、未切分支、未碰 `main`**；`git add` 一律按文件名逐个加（未用 `-A` / `.`）；
commit 信息一律用 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`（三个都复核过 CRLF = 0）。

### 8.7 探针脚本（一律放在 `.superpowers/sdd/…/t8_probes/`，**不在 `backend/` 下**，硬规矩 #108）

| 脚本 | 干什么 |
|---|---|
| `p1_baseline.py` | 把派单里每一条「既有常量的当前值」在当前 HEAD 上实测一次（硬规矩 #111） |
| `p2_timing.py` | 量 `training_days_of` 的吞吐，决定「按层完成率」的取数口径与记忆化 |
| `p3_mutation.py` | `app/domain/report.py` 的 24 条变异取证（跑完按字节还原并复核） |
| `p4_endpoints.py` | 端点计数（`openapi()["paths"]`，**不是** `len(app.routes)`）、security 清单、schema 组件、扫描面 |
| `p5_fix_error_shape.py` | 把 19 处 `resp.json()["code"]` 机械改成 `["error"]["code"]`（改完复核残留 0、新写法 19、无 BOM、CRLF 0） |
| `p6_backfill_elapsed.py` | 按账本既有口径实测 `elapsed`（临时改阈值 → 读回真值 → 按字节还原并复核） |
| `p7_final.py` | 最终验收的全部计数与四个指纹 |

⚠️ 每个都先 `python -m py_compile` 过一遍再跑；`p3` / `p6` 两个会**临时改生产/测试文件**的，
一律先从内存存原字节、`finally` 里写回、写回后按字节复核（不用 `git checkout`）。
"""

TARGET.write_text(BODY, encoding="utf-8", newline="\n")
raw = TARGET.read_bytes()
print("报告:", TARGET)
print("  字节 =", len(raw))
print("  行数 =", raw.count(b"\n"), "（首行 =", repr(raw.split(b"\n")[0][:60].decode("utf-8")), "）")
print("  BOM =", raw[:3] == bytes([239, 187, 191]), " CRLF =", raw.count(bytes([13, 10])))
print("  末行 =", repr(raw.split(b"\n")[-2][:60].decode("utf-8")))
