# Plan 03 Task 7 实现者报告 —— 预警落地：`alert_stage` + `InAppChannel` + `weekly_adjustment` 的 `auto` 来源

**分支** `feature/plan-03-feedback-alert-crud-api`　**基线** `6d0c8d2`　**HEAD** 见第 8 节
**fix round 数：0**（目标 0–1）

---

## 1. 环境与基线复现

### 1.1 硬规矩 #73 的 import 冒烟（开工第一件事）

```
python -c "import sqlalchemy, fastapi, uvicorn, httpx, pydantic, yaml; print(sqlalchemy.__version__, fastapi.__version__)"
→ 2.1.3 0.141.1
```

**没有撞上 `ImportError: DLL load failed`**（Smart App Control 没拦 `.pyd`），故按计划做完。
Python 3.11.1、无 venv。

### 1.2 仓库状态（开工时实测，与派单逐条对上）

| 项 | 派单说 | 实测 |
|---|---|---|
| 分支 | `feature/plan-03-feedback-alert-crud-api` | ✓ 同 |
| HEAD | `6d0c8d2` | ✓ 同 |
| 工作树 | 干净 | ✓ `git status --porcelain` 空 |
| `backend/pe.db` | 不得存在 | ✓ 不存在 |
| `backend/data/seed/` | 0 文件 | ✓ 0 |
| 测试基线 | 1026 passed | ✓ **1026 passed**（129.20 s） |
| 覆盖率基线 | 1147 / 0 / 336 / 0 / 100% | ✓ **逐字相同**（1025 passed, 1 skipped，212.11 s） |
| 表数 | 25 | ✓ 25 |
| `_MODELS_PUBLIC_BASELINE` | 33 | ✓ 33 |
| 扫描面 | 52（pipeline 8 + db 11 + domain 17 + api 16） | ✓ **逐字相同** |
| 端点数 | 56 | ✓ 56 paths / 84 operations |
| 四个指纹 | `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` / `E48E3AC82BB45BB7` | ✓ 四个逐字相同 |

### 1.3 ⚠️ 端点数的**口径**：不能用 `app.routes`（硬规矩 #109 抓到的一次）

我第一次用 `len({r.path for r in app.routes})` 量，得到 **5**——与派单的 56 差一个数量级。
按硬规矩 #109「先用第二个独立工具复核，才允许当成发现」，换 `app.openapi()["paths"]` 复量，
得到 **56**。原因实测：**FastAPI 0.141 把 `include_router` 进来的路由惰性挂在
`_IncludedRouter` 里**，`app.routes` 只有 6 项（4 个 `Route` = docs/openapi/redoc/oauth2-redirect、
1 个 `_IncludedRouter`、1 个 `APIRoute` = `/api/health`）。

⚠️ 于是「端点数」在本仓的**唯一可用口径是 `app.openapi()["paths"]`**；
`app.routes` 那一口径在今天这个 FastAPI 版本上**不可用**。派单的 56 是 openapi 口径。

### 1.4 `refdata_alerts` 的公开面（派单要求自己 `dir()` 一遍）

**3 个名字**：`ALERT_RULES_FILENAME` / `alert_rules` / `load_alert_rules`（无 `__all__`，
故用 AST 数「顶层公开 def/class + 顶层公开赋值」，两种口径一致）。`alert_rules().version == "1.0"`。

---

## 2. P7-A3 的 6 条关切：逐条落地位置

| # | 关切 | 落地位置（`backend/` 下的行） | 守卫 |
|---|---|---|---|
| 1 | `*_skip_traces` 必须有消费者 | `app/pipeline/alert_stage.py`：`_count_skipped()` 把两个 `*_skip_traces` 的返回值累加进 `AlertReport.skipped`；`evaluate_alerts` 末尾那条 `logger.info` 把它印出来（`「判不了」的留痕 %s`） | `test_the_skip_traces_are_consumed_not_just_computed`（断言 `skipped["RED_MINITEST_DROP"] == 1` 与 `skipped["YELLOW_CLASS_RPE_HIGH"] == 1`，**且**两条规则各自 0 行 alert）+ `test_the_skip_traces_reach_the_log_line`（`caplog` 里要有 `RED_MINITEST_DROP` 与「判不了」） |
| 2 | `rpe_session_ids` 必须按时间升序 | `app/pipeline/alert_stage.py::_rpe_rows` 的 `ORDER BY`：`(student_id, session_date, period, submitted_at, id)`；`_rpe_streak` 反向扫描后再 `reverse()`，故返回的元组也是升序 | `test_a_late_submission_does_not_move_the_window_key_anchor`（造「课次时间序 ≠ 提交时刻序」的数据，期望侧是字面的 `f"rpe{cs3}"`）+ 变异 M2（见 §6.4） |
| 3 | `rpe_min` 与 `improve_pct` 由本 Task 消费 | `rpe_min`：`_student_signals` 里 `rules.params_of(RuleId.RED_RPE_SUSTAINED)["rpe_min"]` → 传给 `_rpe_streak`。`improve_pct`：同处 `rules.params_of(RuleId.GREEN_MASTERY)["improve_pct"]` → 传给 `_mini_test_improved` | `test_rpe_min_comes_from_the_rules_not_from_a_literal` 与 `test_improve_pct_comes_from_the_rules_not_from_a_literal`：两条都是「换一套注入的 `AlertRules`，行为跟着变」（生产阈值下不触发、放宽后触发），故**死配置就红** |
| 4 | `completion_rate` 必须夹在 `[0,1]` | `_student_signals`：`completion_rate = min(1.0, len(done) / len(days))` | `test_the_completion_rate_never_exceeds_one`（造一个「在非训练日也打了卡」的学生，让交集真的做功）+ `test_the_completion_rate_numerator_uses_the_same_four_conditions_as_the_endpoint` |
| 5 | `checkin_gap_days` 的「应打卡训练日」复用 Task 5 的 `_training_days_of` | **搬家了**：`_training_days_of` 从 `app/api/routers/feedback.py` 提到 `app/pipeline/prescription_stage.py::training_days_of`（commit `6dc46a7`）。`alert_stage._student_signals` 与 `feedback.completion_rate` 现在**共用它** | `test_training_days_of_has_exactly_one_definition`（AST 数定义份数 == 1，且就在 `prescription_stage.py`）+ `test_the_semester_week_helpers_agree_with_the_api_layer_one` |
| 6 | `AlertRules.params_of` 今天没有生产调用者 | `app/pipeline/alert_stage.py::_student_signals` 的三处调用（`rpe_min` / `improve_pct` / `gap_days`） | `test_params_of_has_a_production_caller`（AST 数 `params_of` 的**调用点**，排除 domain 里那一处定义） |

### 2.1 第 5 条为什么要搬家、搬到哪里（派单授权的那一档）

派单 P7-A3 第 5 条逐字预判了这件事，并授权「提到一个两层都能 import 的住址」。实测确认：
`tests/architecture/test_layering.py::test_api_layer_dependency_direction_is_one_way`
的**反向那一圈**（`SCANNED_DIRS` 减掉 `api`）禁止 `pipeline` import `app.api`，
故 `alert_stage` 拿不到 `feedback.py` 里的私有函数。

**住址选 `app/pipeline/prescription_stage.py`，不是新建一个 `app/` 根下的模块**，三条理由：

1. `api → pipeline` 是许可方向（`API_ALLOWED_PREFIXES` 里有 `"app.pipeline"`），
   而 `feedback.py` **本来就**从这个模块 import `effective_package` 与 `weekly_factors_of`；
2. 它的三个依赖里**前两个就住在 `prescription_stage`**，第三个（`weekly_training_sheet`）
   住在 domain —— 搬过来之后它不再跨任何一层；
3. 新建 `app/` 根下的模块（照 `app/notify.py` 的形状）会要求往 `API_ALLOWED_PREFIXES`
   加一项，而账本 S6 逐字写着「下界由 Task 1 一次抬完，**后面 8 个 Task 不再动它**」；
   `app/domain/` 则收不下它（要 `Session` 与 `dt.date`，而 domain 的 allow-list 连
   `datetime` 都不放行）。

搬家连带两处签名改动（**口径逐字不变**）：`exercises` 从「函数体内调 refdata 单例」改成
keyword-only 必填（`prescription_stage` 的既有纪律是「参考数据由调用方注入」）；
`week_start` 的算式从 `days=(week-1)*DAYS_PER_WEEK` 改成 `weeks=week-1`
（`timedelta(weeks=n) == timedelta(days=7*n)` 逐格相等，而前者要求本模块再持有一份「7」——
本模块的 `valid_to_of` 早就为此用了 `timedelta(weeks=…)`）。
⚠️ `feedback.py` 自己的 `DAYS_PER_WEEK = 7` **没动**：它还服务 `_week_days`（学期周的 7 天）。

零行为变更：`tests/api + tests/architecture + tests/pipeline` 共 **215 passed**。

---

## 3. `alert_stage.py` 与 `notify.py` 的公开面

### 3.1 `app/pipeline/alert_stage.py` —— `__all__` **9** 个

```
ALERT_HANDLED  ALERT_IGNORED  ALERT_PENDING  AUTO_REDUCTION_FACTOR  AUTO_SOURCE
AlertReport    evaluate_alerts  semester_week_of  semester_week_range
```

签名（⚠️ 比简报 Interfaces 多三个 keyword-only 形参，逐条理由见 §6.2）：

```python
def evaluate_alerts(session, semester_id, batch_id, as_of, *,
                    rules: AlertRules,
                    exercises: Mapping[str, ExerciseSpec],
                    now: dt.datetime,
                    channel: NotificationChannel | None = None) -> AlertReport
```

模块内另有两个**被测试直接引用**的私有名：`_write_auto_adjustment`（也被
`app/api/routers/alerts.py` 复用）与 `_counted_checkin_days` / `_reported_checkin_days`。

### 3.2 `AlertReport`（frozen dataclass）—— **6** 个字段

| 字段 | 出处 |
|---|---|
| `raised: int` | 简报逐字。= `daily_sync_run.alert_count` |
| `deduped: int` | 简报逐字 |
| `by_level: dict` | 简报逐字。**稀疏**（计数 0 的级别不出现，口径照 `PrescriptionReport.skipped_reasons`） |
| `adjustments_written: int` | 简报逐字 |
| `skipped: dict` | **本 Task 加的**：P7-A3 第 1 条要求的留痕消费者 |
| `errors: int` | **本 Task 加的**：异常分层第 1 档的可观测量。没有它，「一个学生的数据坏掉了」在报表上与「今天没人触发」同形 |

守卫 `test_the_report_is_frozen_and_has_the_six_documented_fields`
（`dataclasses.fields` 口径数名字与顺序，且 `FrozenInstanceError` 真的抛）。

### 3.3 `app/notify.py` —— `__all__` **8** 个

```
IN_APP  RECIPIENT_STUDENT  RECIPIENT_TEACHER
InAppChannel  NotificationChannel  SmsChannel  WechatSubscribeChannel  now_local
```

* `NotificationChannel` 是 `@runtime_checkable` 的 **Protocol**（不是 ABC）：
  加一个通道不该要求它 import 本模块并显式继承。守卫两条——
  `test_every_channel_satisfies_the_protocol`（`isinstance`）+
  `test_the_protocol_names_the_seven_keyword_arguments`（`inspect.signature` 数 7 个形参、
  6 个 keyword-only、两个缺省 `None`）。⚠️ `runtime_checkable` **只查方法名在不在、
  不查签名**，故两条缺一不可。
* `send` **不 commit、不 flush**（事务边界由调用方掌握，与 `repo.upsert` 同一条口径）。
  守卫 `test_send_does_not_commit`。
* 三个常量都经 `_vocabulary()` 与 `Notification.CHANNELS` / `RECIPIENT_KINDS` **对账**，
  对不上就在 **import 期**响亮失败（而不是等某一次 `send` 落库时被 CHECK 拒收）。
  守卫 `test_the_channel_and_recipient_vocabulary_comes_from_the_model_not_a_second_copy`
  + 反证 `test_an_unknown_channel_is_rejected_by_the_check_constraint`
  + `test_the_three_channels_cover_exactly_the_model_vocabulary`（按**集合相等**）。
* 两个骨架的 docstring 照 `app/adapters/http_lepao.py` 的形状写明「未来实现时必须满足的契约」，
  并逐字抄了那一条警告：**不得沿用「三个实现跑同一组契约测试」这种说法**。

### 3.4 `app/api/routers/alerts.py` —— `__all__` **5** 个

`ACTION_REDUCE / ACTION_IGNORE / ACTION_NOTE / ALERT_NOT_PENDING / router`。
三档动作的**值域所有者**是 `app/api/schemas/alerts.py::HANDLE_ACTIONS`
（`("reduce_20pct", "ignore", "note")`），端点里那三个常量由
`test_the_three_action_constants_are_the_schema_vocabulary` 按**集合相等**与它对账。

---

## 4. `weekly_adjustment` 的 `auto` 来源写入路径

**唯一所有者**：`app/pipeline/alert_stage.py::_write_auto_adjustment(session, *, prescription,
week, rule_id, batch_id, created_at) -> bool`（返回**是否新写**）。两个调用方：
管道的 `evaluate_alerts`（红色预警触发时）与 `POST /api/alerts/{id}/handle`
（教师点 `reduce_20pct` 时）。

### 4.1 三个决定，各挡一个静默失效

**① `factor` 先过值对象**（Plan 02 留给 Plan 03 的第 4 条）：

```python
factor = WeeklyFactor(week=week, factor=AUTO_REDUCTION_FACTOR,
                      reason=rule_id.value, source=AUTO_SOURCE)
```

`weekly_adjustment.factor` 那一列**刻意没有 CHECK**（P8-A6：`(0, 2]` 是读模型的语义、
不是数据的形状），故 `WeeklyFactor.__post_init__` 是写入侧**唯一**的闸门。少了它，
一个 `factor = 0` 会静默落库，然后让学生端打开训练单时在 `weekly_factors_of` 里抛
`ValueError` → **500**（Plan 02 Task 8 的关切 1 逐字就是这个形状）。
`AUTO_REDUCTION_FACTOR = 0.8`（spec §8.4 的字面「减量 20%」），它的住址在
`alert_stage`，**不在 `alert_rules.yaml`**（理由见那个常量的注释：那份 YAML 的键集被
`_PARAM_TYPES` 按「恰好这几个键」钉死，且文件被指纹按字节钉住）。

**② 裸 INSERT + 自己的 SAVEPOINT，让 DB 当去重的裁判**（派单逐字点名的坑）：

```python
try:
    session.flush()                 # ← 进 SAVEPOINT 之前先 flush，见下
    with session.begin_nested():
        session.add(WeeklyAdjustment(prescription_id=…, batch_id=…, week=factor.week,
                                     factor=factor.factor, reason=factor.reason,
                                     source=factor.source, created_at=…))
        session.flush()
except IntegrityError as exc:
    logger.info("处方 %s 第 %s 周已经有一条 %s 的 %s 调整（%s），本次不重复写：…", …)
    return False
return True
```

⚠️ **刻意不用 `repo.upsert`**：`upsert` 是「先 SELECT 再 update/insert」，撞上
`uq_weekly_adjustment_prescription_week_reason_source` 时它**不抛异常**，而是走更新分支、
把 `factor` / `batch_id` / `created_at` 三个非键列 `setattr` 到**已有的那一行**上并返回它。
于是「一次本该被拒绝的重复写入」变成「静默改掉一条已经生效的调整」——而 `created_at`
正是 `weekly_factors_of` 的排序键（`ORDER BY created_at, id`），改它会让同一周上多条
调整的**相乘顺序**跟着变（浮点尾数因此漂，教师端显示的系数也漂）。
裸 INSERT 结构上不可能更新任何行：撞键就是 `IntegrityError`。

⚠️ **进 SAVEPOINT 之前那一句 `session.flush()` 是承重的**：`begin_nested()` 会把此前
所有未落库的写入（本批刚 `add` 的 `alert` 与 `notification`）一并带进这个 SAVEPOINT，
于是它们中间任何一条坏了都会被算到「调整撞键」这一档上。

**③ `IntegrityError` 只回滚它自己的 SAVEPOINT**，然后 `return False` 继续下一个人。
⚠️ **不能裸 `session.rollback()`**：本阶段跑在 `run_daily` 的 `session.begin_nested()` 里，
裸 rollback 会把**整批**（分层 + 快照 + 派生 + 处方 + 本批已写的预警）一起撤销，
而调用方以为只是这一条调整没写进去。

### 4.2 `reason` 的格式：**裸的 `rule_id`**，不带版本号

`reason = rule_id.value`（例如 `"RED_RPE_SUSTAINED"`），`source = "auto"`，
`week = current_week(...)`，`batch_id` = 管道那侧取**本批**、教师那侧取**处方自己的**
（口径逐字见 `WeeklyAdjustment.batch_id` 的列注释）。

⚠️ **这是对 `app/domain/alerts.py` 模块 docstring 那一句的一处有意偏离**（顶回，见 §6.3）：
它写的是「`version` ……Task 7 把它写进 `weekly_adjustment` 的 `auto` 来源留痕」。
而 `reason` 是那条四列唯一约束的**一列**，把版本号拼进去
（`"RED_RPE_SUSTAINED@v1.0"`）会让「专家升一次 YAML 版本号」等价于
「同一周可以再减一次量」→ `0.8 × 0.8 = 0.64`，
**Review Focus 第 3 条要防的连乘从版本号那一侧回来**。约束自己的注释也逐字警告过
「`reason` 是自由文本，改一个标点就绕过了本约束」。

版本号因此落在 **`alert.trigger_snapshot["alert_rules_version"]`**：预警行与调整行是
**同一次触发**的两半（同一条规则、同一周、同一个学生），故「当时按哪一版阈值判的」
仍然可以离线复核，而不必把版本塞进去重键。
守卫 `test_the_reason_carries_no_version_so_the_unique_key_stays_stable`。

### 4.3 撞键判定与 rollback 的那条测试名

**`test_a_duplicate_auto_adjustment_is_rejected_by_the_db_not_silently_updated`**
（`backend/tests/pipeline/test_alert_stage.py`）。它先手工插一条同
`(prescription_id, week, reason, source)` 的调整，带一个可辨认的 `created_at`
（`2020-01-01 00:00`）与**另一个真实存在的** `batch_id`，然后跑一次会触发红色预警的求值，
断言三件事：① 不抛；② 库里仍是一行、`adjustments_written == 0`；
③ **已有那一行的三个非键列一个都没被改**（`factor == 0.9`、`created_at == marker`、
`batch_id == other_batch`）。第 ③ 件正是「换成 `repo.upsert` 就会红」的那一件。

⚠️ 教师那侧的同一档由
`tests/api/test_alerts_api.py::test_reduce_20pct_after_the_pipeline_already_reduced_does_not_multiply`
看着：管道已经减过 → 教师再点一次 → HTTP **200**、`adjustment is None`、
库里仍是一行 `factor == 0.8`。

### 4.4 处方到期那一档

`current_week(...) is None` → **不写**调整，只在 `alert.trigger_snapshot` 里留痕
`"prescription_expired": true` + 一条 `warning` 日志。理由照简报：给一张已到期的处方写
「本周减量」没有意义，而 spec §5.2 的触发 3 会在同一天生成新处方。
守卫 `test_no_adjustment_when_the_prescription_has_expired`
（⚠️ 断言的是「预警本身照落、只有调整不写」：到期只影响「要不要减量」，不影响「要不要报」）。

---

## 5. `_replay_cleanup` 的清单：5 → **6** 张

### 5.1 ⚠️ 顶回派单的一处：它**已经是 5 张**，不是 3 张

派单 P7-A2 写「本 Task 要把那个元组扩到 5 张」，并引了 `:755` 那条注释作依据。
按硬规矩 #111（「派单里每一个『既有常量的当前值』都要在当前 HEAD 上实测一次」）
用 AST 数了那个元组的项数：

```
元组项数 = 5   顺序 = ['models.DerivedMetrics', 'models.StratificationResult',
                      'models.PercentileSnapshot', 'WeeklyAdjustment', 'Prescription']
```

即 **Plan 02 Task 7 早就把它从 3 张扩到 5 张了**（`_replay_cleanup` 自己的 docstring
逐字写着「Plan 02 Task 7 把清单从三张扩到五张（P7-A4）」）。派单那句话把**已完成**的
那一次扩表当成了本 Task 的活。本 Task 加 `Alert` → **6 张**（与简报 Task 7 的 Files 行
「`_replay_cleanup` 加 `Alert`」一致）。

`:755` 那条注释按**实际发生的事**改写了：它此前印的是「五张带 batch_id 的表
（Plan 01 的三张派生表 + Plan 02 Task 6 的 prescription / weekly_adjustment）」，
现在印「六张（…… + Plan 03 Task 7 的 alert）」，并把「待清扫第 3 条，Task 9 结案」
那半句**就地结案**（改成如实的历史陈述：本处的张数过期过两次）。
另附一句限定：另两张带 `batch_id` 的表（`class_session` / `training_log`）那一列**可空**
（P5-A1），且 `daily.py` 今天一个字节都不往它们写，故不在这六张里。

顺带把这次扩表弄过期的**另外四处**计数改成如实的（都在 `daily.py` 内）：
模块 docstring 首行的阶段序列（加 `→ Alert`）、「七个阶段共用一个原子边界」→ 八个、
「重放清理是五张派生表」→「清理清单里的六张表」、三处「七个阶段的计数看起来全都正常」→ 八个、
`main()` 的 argparse `description`（加 `→ Alert`），并在 `main()` 里补一行
`预警：本日新触发 {run.alert_count} 条`（与处方那一行同一条口径）。

### 5.2 顺序

```
models.DerivedMetrics → models.StratificationResult → models.PercentileSnapshot
→ WeeklyAdjustment → Prescription → Alert
```

* **承重的那一对**仍是 `WeeklyAdjustment` → `Prescription`（**子表先删**：
  `weekly_adjustment.prescription_id` 是外键指向 `prescription.id`，
  而 SQLite 跑在 `PRAGMA foreign_keys=ON` 下，先删父表当场 FK 违例）。
  既有守卫 `test_replay_cleanup_covers_prescription_and_weekly_adjustment` 的正反两段仍在。
* **`Alert` 排在末尾，而这一格不承重**：清单里没有任何一张表的外键指向 `alert`
  （`notification.alert_id` 带 `ON DELETE SET NULL`，而 `notification` **不在**清单里），
  而 `alert` 自己的四个外键指向 `student` / `course_section` / `semester` /
  `daily_sync_run`，四张都不在清单里。故排末尾只是书写序（理由写在那个元组的注释里）。
* 前三张（Plan 01 那三张派生表）之间没有 FK 关系，相对顺序不承重，按 Plan 01 的书写序不动。

### 5.3 `ClassSession` 确实**不在**里面

AST 复核：`ClassSession 在里面: False`。
理由逐字见 `app/db/models/feedback.py` 的模块 docstring：`rpe_record.class_session_id`
是 **NOT NULL 的外键**指向它，而 `rpe_record` 是学生实时写入的、刻意不带 `batch_id`。
按批删课次只有两种结局：当场 `FOREIGN KEY constraint failed`，或者把那一列改成
`ON DELETE CASCADE`——那会连带删掉学生刚交的快评（删源数据 vs 删派生行）。
它的幂等手段是 `repo.upsert` 按 `(course_section_id, session_date, period)` 更新。

**新增守卫** `test_replay_cleanup_still_does_not_cover_class_session`：
造一行**带 `batch_id`** 的 `ClassSession`，跑 `_replay_cleanup`，断言它还在。
⚠️ 这一条今天之前**没有任何测试看着**（`ClassSession` 的 `batch_id` 是 Task 5 才改可空的，
而「不得进清单」这件事此前只写在三个 docstring 里）——它现在是可执行的。

### 5.4 `Alert` 能进清单的前提是那条 `ON DELETE SET NULL`

`notification` **刻意不带** `batch_id`、不在清单里（消息是已经推给某个人的东西，
重放那天按批删掉它，学生端消息中心的红点会凭空消失），而 `notification.alert_id`
指着 `alert`。普通外键会让清理当场 `FOREIGN KEY constraint failed`、整批回滚；
`CASCADE` 则会连带删掉已经推出去的消息。`SET NULL` 是唯一同时满足「重放不炸」与
「消息不丢」的那一档（Task 2 顶回 3）。

**两条守卫**：`tests/test_notify.py::test_a_notification_survives_the_deletion_of_its_alert`
（单元级：删 alert → 消息还在、`alert_id` 变 NULL）与
`tests/pipeline/test_alert_stage.py::test_replay_cleanup_covers_alert_and_leaves_the_notification_alone`
（**在清理路径上**：跑真的 `_replay_cleanup` → alert 与 weekly_adjustment 都空、
notification 活下来且断开关联、且没抛 FK 错）。

### 5.5 漏掉 `Alert` 的失效形态（与处方表那次**不同**）

`prescription` / `weekly_adjustment` 漏删是**翻倍**；`alert` 漏删**不翻倍**
（四列唯一约束挡着，且本模块先 SELECT 后 INSERT）——它失效成
「**静默地不再报**」：重放那一天会在 SELECT 上命中已有行、计入 `deduped`，
于是「重放那一天」与「那一天真的没人触发」在 `alert_count` 上同为 **0**，
而重放的定义是「同一批输入得到同一批输出」。这一段写进了那条守卫的 docstring。

---

## 6. 待清扫 / 关切 / 没按派单做的地方 / 顶回

### 6.1 待清扫（**4 条**，都是纯散文精度，按 Ruling 5 不在本 Task 修）

1. **`app/db/repo.py::delete_by_batch` 的 docstring 有两处被本 Task 弄过期的计数**：
   「全库只有九张表有这一列」下面那句「`_replay_cleanup` **今天清的是上面九张里的五张**
   （Plan 01 的三张 + Plan 02 的两张……）」→ 现在是**六张**；
   以及「Plan 03 那四张里，`Alert` 与 `WeeklyClassReport` **由 Task 8 接进清单**」→
   `Alert` 已由 **Task 7** 接进。
   ⚠️ 同一处 docstring 里还有一段是**它自己批评过的形状**（「留一个不兑现的预告」），
   故这一条建议 Task 9 一并改成如实的。
2. **`app/db/models/feedback.py` 的模块 docstring 与 `Alert.batch_id` 的列注释**各有一处
   「Task 8 会把 `Alert` 接进 `_replay_cleanup`」/「Task 8 可以照常接进清单」→ 是 Task 7。
   `Notification.alert_id` 的列注释同理（「Task 8 会把 `Alert` 加进 `_replay_cleanup`」）。
3. **`app/pipeline/prescription_stage.py` 的模块 docstring** 有一处
   「`source = "auto"`（spec §8.4「预警触发减量 20%」）**也留给 Plan 03**」与
   「本阶段**不写** `weekly_adjustment` 行」——前半句现在已兑现（本 Task 就是那个 Plan 03），
   后半句对 `prescription_stage` 本身仍然为真（写它的是 `alert_stage`），
   但读的人容易以为「auto 到今天还没有写入方」。`WeeklyAdjustment.batch_id` 的列注释里
   「生产写入方今天仍为**零**」同样过期（`"auto"` 有了，`"teacher"` 仍为零）。
4. **`app/api/routers/feedback.py` 有 4 个死 import**（AST 实测，**基线 `6d0c8d2` 上就有**，
   用 `git show` 复核过：四个名字在基线版本里各只出现 1 次，即只在 import 行）：
   `MiniTestBatchFailure` / `NormalizedSectionRead` / `RpeSubmissionRead` /
   `UnassignedEntryRead`。**不是本 Task 造成的**，故不在本 Task 动它
   （本 Task 只删了自己弄成死的那 4 个：`effective_package` / `weekly_factors_of` /
   `weekly_training_sheet` / `Prescription`）。

### 6.2 没按派单做的地方（**3 处**，逐条理由）

1. **`evaluate_alerts` 的签名多了 3 个 keyword-only 形参**（派单/简报给的是
   `(session, semester_id, batch_id, as_of, *, rules)`）。那个签名**跑不起来**：
   * `now` —— `alert.triggered_at` 与 `notification.created_at` 都是 `DateTime NOT NULL`
     **且无缺省**（本仓全部表的统一约定：时钟由调用方注入，守卫
     `test_the_plan03_tables_inject_the_clock_and_never_default_it`）。⚠️ 而它必须是
     **一个**时刻：`weekly_factors_of` 按 `created_at` 排序，三个时刻列若来自三次
     `now()`，同一批里「预警触发」与「减量生效」的先后就会随调用点漂。
   * `exercises` —— `training_days_of` 要它，而 `prescription_stage` 的既有纪律是
     「三份参考数据一律由调用方注入」（`generate_prescriptions` / `effective_package` 都是）。
   * `channel` —— 可注入的通知通道，缺省 `InAppChannel`。有它，「红色预警一条消息都不发」
     这类断言不必去查 `notification` 表（守卫 `test_a_channel_can_be_injected`）。
2. **`AlertReport` 是 6 个字段、不是简报的 4 个**。多出的两格各有出处：
   `skipped` 是 P7-A3 第 1 条**要求**的消费者（派单逐字：「把它们的计数写进本 Task 的
   `AlertReport`」）；`errors` 是异常分层第 1 档的可观测量（没有它，「一个学生的数据坏掉了」
   在报表上与「今天没人触发」同形，而那条 warning 日志只有跑的时候才看得见）。
3. **`daily.py` 的日志落在 `alert_stage` 而不是 `run_daily`**。派单 P7-A3 第 1 条写的是
   「在 `run_daily` 的日志里印一行」。实际落在 `evaluate_alerts` 末尾那条 `logger.info`
   （logger 名 `app.pipeline.alert_stage`）——照 `generate_prescriptions` 的既有先例：
   **阶段自己印自己的计数**，`run_daily` 一条阶段日志都不印（它连处方计数都只在
   `main()` 的 CLI 里 `print`）。⚠️ 派单要的那件事（留痕有消费者、且进日志）已经兑现，
   只是住址按既有先例放在阶段里；`main()` 的 CLI 也补了一行 `预警：本日新触发 N 条`。

### 6.3 顶回控制者的地方（**5 处**）

> ⚠️ Ruling 5：Plan 03 的独立评审席折进了控制者亲验，故本节的顶回是唯一的独立视角。
> 共同点是「控制者对着**文档的形状**推理，实现者对着**守卫实际能抓到什么**推理」。

1. **【Important】`_replay_cleanup` 的元组在 HEAD 上已经是 5 项，不是 3 项**（派单 P7-A2）。
   AST 实测见 §5.1。派单引的那条 `:755` 注释**自己**就是过期的证据：它说
   「Task 7 把 `_replay_cleanup` 扩到五张之后就过期了」——而 Plan 02 Task 7 早就扩完了，
   故那句话在 Plan 02 结案当天就已经是在预告一件**已完成**的事。
   本 Task 的实际动作是 **5 → 6**（加 `Alert`），与简报 Task 7 Files 行一致。
2. **【Important】扫描面是 52 → **54**，不是派单预测的 53。**
   派单的推理是「`app/notify.py` 在 `app/` 根下、不在 `SCANNED_DIRS` 任何一项里，
   故只有 `alert_stage.py` 让它涨」——那半句对，但**漏了 `app/api/routers/alerts.py`**，
   而派单自己在第 4 节逐字要求本 Task 创建它（S1 的裁定）。`api` 在 `SCANNED_DIRS` 里，
   故它也让扫描面涨一格。实测：pipeline 8→**9**、db 11、domain 17、api 16→**17** = **54**。
3. **【Important】RPE 的排序键是「课次时间」，不是派单 P7-A3 第 2 条写的 `submitted_at`。**
   `submitted_at` 是**学生按下提交键**的时刻，不是那节课的时刻；而 `submit_rpe`
   **刻意不做过期**（它 docstring 的「刻意不做」第 2 条），故一节早先的课完全可以在
   一节晚近的课**之后**才被提交。那时按 `submitted_at` 排会把迟到的那条排到元组**末尾**，
   `window_key` 的锚点从 `S3` 移到 `S2` → 键变 → **同一次「连续 ≥ 9」第二次落库** →
   连乘回来。即：派单那条关切要防的失效，**按派单给的方子反而会引入它**。
   故 `ORDER BY` 取 `(session_date, period)`（那才是「连续 3 次**课堂**快评」的时间轴），
   `submitted_at` 与 `id` 只作同节课内的 tie-breaker。
   守卫 `test_a_late_submission_does_not_move_the_window_key_anchor` + 变异 M2（只它一条红）。
4. **【Important】`reason` 不带 YAML 版本号**（与 `app/domain/alerts.py` 模块 docstring
   那一句相反）。逐字理由与失效算式见 §4.2：`reason` 是四列唯一约束的一列，
   把版本拼进去等于让「升一次版本号」= 「同一周可以再减一次量」→ `0.64`。
   版本号改落 `alert.trigger_snapshot["alert_rules_version"]`，可追溯性没有损失。
5. **【Minor】`checkin_gap_end` 锚在「凑满 `gap_days` 那一天」，不是 domain docstring
   字面写的「那段中断的**结束日**」。** 按字面读法键会**天天变**：一个 5 天的中断会落
   4 条 `alert`——Review Focus 第 3 条要防的形状从打卡这一侧回来了。
   故取 `missed[gap_days - 1]`，与 domain 给 `RED_RPE_SUSTAINED` 选
   `rpe_session_ids[streak - 1]` 是**同一条判断**。
   守卫 `test_the_gap_anchor_is_the_day_the_gap_reached_the_threshold`。

### 6.4 变异自证（Ruling 1 只要求 Task 6 做；本 Task 廉价自证 3 条）

脚本 `.superpowers/sdd/…/t7_probes/p3_mutations.py`（读原字节 → 打变异 → 跑测试 →
按字节写回 → 复核 `read_bytes() == 原字节`，**不用 `git checkout`**）：

| 变异 | 目标守卫 | 颜色 | 整文件 |
|---|---|---|---|
| **M1** 「先 SELECT 后 INSERT」→ 恒不 dedup（等价于换 `repo.upsert` 的更新分支） | `test_running_the_same_day_twice_does_not_duplicate_anything` | **RED** ✓ | 21 failed / 12 passed |
| **M2** `ORDER BY` 课次时间 → `submitted_at` | `test_a_late_submission_does_not_move_the_window_key_anchor` | **RED** ✓ | **1 failed / 32 passed** |
| **M3** 绕过 `WeeklyFactor` 值对象直接写系数 | `test_the_auto_factor_passes_through_weekly_factor_validation` | **RED** ✓ | 11 failed / 22 passed |

⚠️ **M2 是最干净的一条证据**：变异只让**该抓它的那一条**红，其余 32 条全绿——
即那条守卫既不是恒绿的、也没有过度确定。M1 / M3 红一大片是预期的
（去掉去重与去掉写入侧校验各自会破坏很多断言），故它们的证据强度低于 M2，如实记录。
⚠️ `test_the_auto_factor_passes_through_weekly_factor_validation` **本身**就是一条
in-test 变异（`monkeypatch.setattr(stage, "AUTO_REDUCTION_FACTOR", 0.0)` → 断言
`ValueError` 且库里 0 行），M3 是它的第二次独立取证（改掉值对象那一步本身）。

### 6.5 关切（**6 条**，硬规矩 #39）

1. **求值人群 = 本学期在三源里留过痕的学生**，不是 `student` 表的每一个人。
   两条理由（正确性 + 性能）与逐字口径写在 `alert_stage` 的模块 docstring。
   ⚠️ **代价**：一个本学期从没在任何一源里留过痕的学生**不会**被求值——
   系统分不清「他不用这个系统」与「他这周没练」。
   ⚠️ **性能理由是实测驱动的**：`GREEN_MASTERY` 与 `YELLOW_CHECKIN_GAP` 都要
   `training_days_of`（= 装配训练包，一次额外的 SELECT + 反解一个约 500 键的嵌套 JSON），
   而 `tests/pipeline/test_backfill.py` 的 `elapsed < 90` 在 Task 5 结案时实测已到
   **47.33 / 47.96 s**（全量跑口径，余量仅 1.88×，硬规矩 #42 的线是 2×）。
   全员求值会让 500 人 ×112 业务日多跑约 **56 000** 次装配。
   **本 Task 实测**（单跑、不带 `--cov`、探针 `p5_backfill_elapsed.py`，取证手段照账本
   Ruling 12：临时把阈值改成必然红的 `1`、从 assert 输出读回真值、跑完按字节还原并复核）：
   `elapsed` = **31.63 s**（Plan 02 的单跑基线是 28.86–29.59 s）→ Alert 阶段约 **+2 s（+7%）**，
   对 90 的余量 **2.85×**。
2. **打卡那一源用了两个不同的窗口**：喂**信号**的按 `_CHECKIN_LOOKBACK`（三周）收窄，
   喂**人群**的只按 `semester.start_date` 收窄。⚠️ 用同一个窗口会漏掉最该被提醒的那一类人
   （连续失联四周的学生在三周窗口里一行都没有 → 不在人群里 → `YELLOW_CHECKIN_GAP`
   对他**永远不触发**）。这一格是写代码时发现的、派单没有点出来，理由写在
   `evaluate_alerts` 体内 `onboarded` 那一处的注释里。
3. **完成率与打卡中断用了两套「什么算打过卡」**：完成率严格（`completed ∧ ¬late ∧
   ¬is_rest_day ∧ ¬补卡`，与端点逐字同口径，因为它是 spec 点名的 RCT 过程指标），
   中断宽松（`completed ∧ ¬is_rest_day`，因为问的是「是不是失联了」）。
   ⚠️ **代价**：一个天天迟交的学生完成率永远不达标（拿不到绿牌）、也永远不会被提醒补练
   ——两套口径对他给出两个方向相反的结论。理由与守卫见 `_reported_checkin_days` 的 docstring。
4. **完成率的四个条件有两个所有者**（`alert_stage._counted_checkin_days` 与
   `feedback.completion_rate` 的分子）。**并存而不合并**，处置照
   `AlertLevel`（domain）与 `Alert.LEVELS`（DB）的先例：那一处住在 `app/api/`
   （本模块反向 import 不到），而它是端点响应体的算法本体、抽出来会让端点读不懂。
   由 `test_the_completion_rate_numerator_uses_the_same_four_conditions_as_the_endpoint`
   钉成逐字相等（四个条件各造一行违例）。⚠️ **改其中一处而不改另一处，那条测试会红。**
5. **`min(1.0, …)` 那个夹取今天不可达**：分子是 `counted ∩ 本周训练日`、分母就是
   「本周训练日」，故分子结构上不可能超过分母。仍写下是因为**它是那个交集的护栏**：
   谁哪天把交集去掉（例如改成「按学期周算分子、按处方周算分母」），比率就会越过 1，
   而 domain 的 `>=` 会静默开始与 spec 的「100%」不等价（Task 6 顶回 6 那条论证的前提）。
6. **`weekly_adjustment.source` 回答不了「这一条是管道写的还是教师点的」**：
   `POST /api/alerts/{id}/handle` 的 `reduce_20pct` 也写 `source="auto"`
   （理由与失效算式见 §4 与那个 router 的模块 docstring：写 `"teacher"` 会让四列唯一约束
   拦不住它 → `0.8 × 0.8`）。要区分请读 `alert.handled_action` 与 `alert.handled_at`。
   ⚠️ 连带：`WeeklyAdjustment.SOURCES` 里的 `"teacher"` **今天仍然没有生产写入方**
   （`weekly-adjustments` 在 CRUD 目录里是 `writable=False`，教师覆盖走的是
   `prescription.teacher_overrides` 列）——与 `"auto"` 当初的处境一样，
   它进值域的理由是「届时往一个已结案的 CHECK 里加值等于重建库」。

---

## 7. 最终验收

| 项 | 基线 | 现在 | 判定 |
|---|---|---|---|
| `python -m pytest -q` | 1026 passed | **1097 passed**（105.20 s） | ✓ **+71，零回归** |
| `--cov=app.domain --cov-branch` 四格 | 1147 / 0 / 336 / 0 / 100% | **1147 / 0 / 336 / 0 / 100%** | ✓ **逐字不变**（1096 passed, 1 skipped；本 Task 不加 domain 代码） |
| 表数 | 25 | **25** | ✓ 本 Task 不建表 |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33** | ✓ 没动 |
| 扫描面 | 52（8+11+17+16） | **54**（pipeline **9** + db 11 + domain 17 + api **17**） | ⚠️ 涨 2，派单预测 53（漏算 `api/routers/alerts.py`，见 §6.3 顶回 2） |
| 端点数（`openapi()["paths"]`） | 56 | **57**（operations 84 → **85**） | ✓ +1 = `POST /api/alerts/{alert_id}/handle` |
| `_replay_cleanup` 的清单 | 5 张 | **6 张**（+ `Alert`，`ClassSession` 仍不在里面） | ✓ |
| 四个指纹 | 见 §1.2 | **四个逐字不变**，且 `crlf=0`、字节数不变（21412 / 23247 / 8245 / 6037） | ✓ |
| `git diff 6d0c8d2 HEAD -- backend/data` | — | **空**（退出码 0；`git status --porcelain -- backend/data` 也空） | ✓ |
| `backend/pe.db` | 不存在 | **不存在** | ✓ |
| `backend/data/seed/` | 0 文件 | **0 文件** | ✓ |
| 架构守卫 | 全绿 | **全绿**（`tests/architecture` 8 passed） | ✓ pipeline 层是黑名单制，`alert_stage` 自由 import `app.domain.alerts` / `app.refdata_alerts` / `app.notify`；`app/api/routers/alerts.py` import 的 5 个 `app.*` 前缀全在 `API_ALLOWED_PREFIXES` 里 |

### 7.1 新增的 71 条测试

| 文件 | 条数 |
|---|---|
| `backend/tests/test_notify.py`（新） | **14** |
| `backend/tests/pipeline/test_alert_stage.py`（新） | **36** |
| `backend/tests/api/test_alerts_api.py`（新） | **21** |
| 合计 | **71** |

简报 Step 1–6 点名的 9 条测试**逐条都有**（`test_alert_count_lands_in_daily_sync_run` /
`test_the_same_trigger_raises_one_alert_not_three` /
`test_a_red_alert_writes_an_auto_adjustment_of_0_8` /
`test_no_adjustment_when_the_prescription_has_expired` /
`test_the_auto_factor_passes_through_weekly_factor_validation` /
`test_a_yellow_gap_sends_a_notification_automatically` /
`test_a_red_alert_does_not_notify_until_the_teacher_acts` /
`test_handling_an_alert_twice_is_409` /
`test_a_per_student_failure_does_not_roll_back_the_batch`）。

### 7.2 撞红的既有守卫（**1 条**，不是派单预测的那一条）

派单预测「`backend/tests/api/test_crud.py`（若路由数断言会红）」。**实际红的是
`tests/api/test_prescription_api.py::test_the_identity_headers_are_registered_as_openapi_security_schemes`**
的 ③ 那一拍（「除特例清单之外，`/api/` 下的端点一个都不带 `security`」）。
那条守卫的 docstring 逐字写着「Task 7/8/9 每加一个带身份的特例端点都要回来往这份清单里
加一行——**这是有意的**：它逼着『哪些端点要身份』这件事有一份可读的全貌」。
故按其设计登记一行（`expected` 清单 11 → **12** 项），并把它 docstring 里的项数与
「Task 7/8/9」改成如实的。`test_crud.py` **一条都没红**（23 个资源与五个端点的形状没变）。

### 7.3 自查（本 Task 碰过的 11 个文件的死 import，AST 口径）

探针 `p6_unused_imports.py`：本 Task **新建/改动**的 10 个文件里，
9 个是 0 个死 import；`tests/api/test_alerts_api.py` 曾有 2 个（`create_engine` / `init_db`，
夹具来自 conftest），**已删**。
唯一剩下的 4 个在 `app/api/routers/feedback.py`，**基线 `6d0c8d2` 上就有**
（用 `git show` 复核：四个名字在基线版本里各只出现 1 次），已记进待清扫第 4 条。

---

## 8. commit sha

| sha | 一句话 |
|---|---|
| `7228868` | **① `feat(notify)`** —— `app/notify.py`（`NotificationChannel` Protocol + `InAppChannel` + 两个未来通道骨架，值域与模型类常量对账）+ 14 条测试 |
| `6dc46a7` | **前置 `refactor(prescription)`** —— `_training_days_of` 从 `app/api/routers/feedback.py` 搬到 `app/pipeline/prescription_stage.py::training_days_of`（架构守卫禁止 `pipeline` import `app.api`；零行为变更，215 passed） |
| `480a36e` | **② `feat(alerts)`** —— `app/pipeline/alert_stage.py`（组装 Signals → 调 domain → 落 alert → 发消息 → 写 `weekly_adjustment` 的 `auto` 来源）+ 33 条测试 + 3 条变异自证 |
| `196a00e` | **③ `feat(api)`** —— Alert 阶段接进 `daily.py`（阶段序列 6→7、`run.alert_count`、`_replay_cleanup` 5→6 张、五处过期计数改成如实的）+ `POST /api/alerts/{alert_id}/handle` + `AlertHandleCreate` / `AlertHandleResult` + 24 条测试（21 新 + 3 补进 `test_alert_stage.py`）+ 登记那条 OpenAPI security 清单 |
| 收尾 | **④ `docs(sdd)`** —— 本报告 + 6 个探针脚本（`p1_baseline` / `p2_endpoints` / `p3_mutations` / `p4_acceptance` / `p5_backfill_elapsed` / `p6_unused_imports` + `write_msg`），以及删掉 `tests/api/test_alerts_api.py` 里那 2 个死 import |

⚠️ 建议 3–4 个 commit，实际 **5** 个：多出来的一个是 `_training_days_of` 的搬家
（它改的是 Task 5 的文件、且是零行为变更的重构，与 commit ② 的新代码混在一起会让
评审看不清哪一半是重构）。

**没有 push，没有切分支，没有碰 main。**
