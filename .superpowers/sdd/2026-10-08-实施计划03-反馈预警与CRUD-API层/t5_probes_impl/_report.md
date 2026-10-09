# Plan 03 Task 5 结案报告 —— §8.1 三源采集的特例端点

**分支** `feature/plan-03-feedback-alert-crud-api`　**基线** `acd3f53`　**结案** `__HEAD__`
**结论** 910 → **956 passed**（+46，零退步）；`app/domain/` 覆盖率四格**逐字不变**
（996 stmts / Miss 0 / 288 branch / BrPart 0 / **100%**）；七个端点上线；
变异自证 **11/11 RED**；真 uvicorn + 真磁盘库端到端冒烟 **28/28 全绿**；
三个指纹**逐字不变**；`git diff acd3f53 HEAD -- backend/data` **为空**；`pe.db` **不存在**。

---

## ① 环境与基线复现

### 1.1 硬规矩 #73 的 import 冒烟（开工第一件事）

```
python -c "import sqlalchemy, fastapi, uvicorn, httpx, pydantic, yaml; print(...)"
→ 2.1.3 0.141.1 2.13.5 0.54.0 0.28.1 6.0.3
```

| 包 | 实测版本 | 与派单一致 |
|---|---|---|
| Python | 3.11.1（无 venv） | ✅ |
| SQLAlchemy | **2.1.3** | ✅ |
| FastAPI | **0.141.1** | ✅ |
| Pydantic | **2.13.5** | ✅ |
| uvicorn | 0.54.0 | ✅ |
| httpx | 0.28.1 | ✅ |
| PyYAML | 6.0.3 | ✅ |
| Starlette | **1.7.0** | ✅（⚠️ 见 §6 的口径发现） |

**没有撞上 `ImportError: DLL load failed`**（Smart App Control 未拦 `.pyd`），故未触发
「立刻停手交回控制者」那一档。`zoneinfo` 可用，`ZoneInfo("Asia/Shanghai")` 与
`datetime.now(z)` 都正常，与控制者的预检一致。

### 1.2 基线复现（在 `acd3f53` 上亲跑）

| 项 | 派单给的基线 | 本机实测 | 一致 |
|---|---|---|---|
| `python -m pytest -q` | 910 passed | **910 passed** / 106.43 s | ✅ |
| `--cov=app.domain --cov-branch` 四格 | 996 / 0 / 288 / 0 / 100% | **996 / 0 / 288 / 0 / 100%** | ✅ |
| 表数 | 25 | **25** | ✅ |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33**（见下方口径说明） | ✅ |
| 扫描面 | 50 | **50** | ✅ |
| `/api/` 路径模板 / 操作数 | 51 / 77 | **51 / 77** | ✅ |
| 工作树 | 干净、HEAD = `acd3f53` | ✅ | ✅ |

⚠️ **`_MODELS_PUBLIC_BASELINE` 的口径**（硬规矩 #103：两种口径以守卫那一种为准）：
`len([n for n in dir(app.db.models) if not n.startswith("_")])` 实测是 **39**，
而守卫
`test_models_public_namespace_is_unchanged_by_the_split` 断言的是
`observed - _MODELS_SUBMODULES == set(_MODELS_PUBLIC_BASELINE)`，
即**减掉 6 个子模块名**（`assessment` / `derived` / `feedback` / `ops` /
`organisation` / `prescription`）之后是 **33**。39 − 6 = 33 ✅ 逐字吻合。
裸 `dir()` 那个口径**不是**基线口径，报告里标注为「不可直接比对」。

### 1.3 Ruling 12 落地后的 `elapsed` 实测值

**函数名已改**：`test_backfill_500_students_under_60_seconds` →
**`test_backfill_500_students_under_90_seconds`**（断言 `assert elapsed < 90`）。

**取证手段**（不留 print、不留插件、不改被测代码的行为）：把阈值临时改成必然红的 `1`，
从 pytest 的 assert 输出里读回 `elapsed` 真值，跑完改回。这样量到的是**全量跑口径**下
的真实值（那才是「全量绿」这个判据所处的负载环境）。

| 跑法 | n | `elapsed` 实测 | 对旧阈值 60 的余量 | 对 90 的余量 |
|---|---|---|---|---|
| 全量 `pytest -q`（910 条，**不带** `--cov`） | 2 | **47.33 s** / **47.96 s** | 1.27× / **1.25×** | 1.90× / **1.88×** |
| 单跑 `tests/pipeline/test_backfill.py -k under_90` | 1 | setup 45.60 s（`elapsed` ≈ 44.9 s） | — | — |
| 全量 `--cov=app.domain --cov-branch` | 1 | 被 `sys.gettrace()` 分支 **skip** | — | — |

⚠️⚠️ **控制者预检报的「全量跑会把它推过 60 s（61.58 / 62.72）」在本机没有复现**：
本机全量跑的最坏值是 **47.96 s**，对 60 s 的余量是 **1.25×**——即它**没有真的红过**，
只是余量薄。**但 flaky 的诊断依然成立，依据从「越界」换成「余量」**：1.25× 远低于
硬规矩 #42 的 2× 线，而「结论会被机器负载翻转」这件事不需要它先红过一次才算数
（Plan 02 Task 7 的 115.08 s 已经证明本机同一份代码的极差可以远超 2×）。
docstring 里因此把这一条如实改写成「未复现 + 依据换成余量」，**没有**把控制者的
两个数写成我亲跑的值（硬规矩 #6）。

⚠️ **顶回的一个数据点**：若只按本机最坏值算，满足 2× 线的阈值是 **96 s**
（47.96 × 2），而 96 仍抓得住 115.08 那次退化——即**在本机上 96 严格优于 90**。
仍按裁定落 **90**，因为控制者那台机器观测到 62.72 s（对它 96 也只有 1.53×，同样不到
2×），而「两台机器都要抓得住 115.08」把阈值上界钉在 115 以下。
**要抬到 96 请连同控制者那台机器的复测一起做。**

**连带同步（硬规矩 #66）**：旧函数名在 `app/` 下还有 **2 处**引用
（`app/pipeline/backfill.py` 与 `app/pipeline/daily.py` 的 docstring），
一并改掉；改完全仓 AST/grep 复核**旧名命中 0 处**（探针 `t5_probes/r12_verify.py`）。

---

## ② schema 变更（P5-A1 / A3 / A4 / A6 + 一列派单没点到的）

全部数字取自探针 `t5_probes/schema_probe.py` 的**运行时口径**。

### 2.1 P5-A1：两张表的 `batch_id` 改可空

| 表 | 改前 `nullable` | 改后 `nullable` | 仍指向 | 仍有索引 |
|---|---|---|---|---|
| `class_session` | `False` | **`True`** | `daily_sync_run.id` | ✅ |
| `training_log` | `False` | **`True`** | `daily_sync_run.id` | ✅ |
| 其余七张（`alert` / `derived_metrics` / `percentile_snapshot` / `prescription` / `stratification_result` / `weekly_adjustment` / `weekly_class_report`） | `False` | **`False`（未动）** | `daily_sync_run.id` | ✅ |

⚠️ 探针把**九张全列出来了**，就是为了证明「只改了两张」而不是「顺手把九张都放宽」
——后者会让 `_replay_cleanup` 的按批删对派生表也失效（那些表只有一个来源，
`NULL` 对它们没有任何用处，只会让「漏填 batch_id」变成一个静默的漏删）。

**`_BATCH_OWNED_TABLES` 那条守卫不受影响**（实测 `test_only_batch_owned_tables_expose_batch_id`
仍绿）：它的判据是「**有** `batch_id` 列的表恰好是那九张」+「FK 指向 `daily_sync_run.id`」，
可空性既不改变列的存在、也不改变 FK 的目标。

**P5-A1 的论证有反证**（不是只在 docstring 里说）：
`test_a_session_created_over_http_has_a_null_batch_id_and_survives_replay` 与
`test_a_student_checkin_has_a_null_batch_id_and_survives_replay` 各自
**真的调一次** `repo.delete_by_batch` 并数返回值 —— 一个带批次的行被删（返回 1）、
实时写的那一行留着。⚠️ 这一条是必要的：「`NULL = 任何值` 不成立」是一句关于
**SQL 三值逻辑**的断言，而三值逻辑恰恰是最容易「以为成立其实不成立」的一类
（某些 ORM 会把 `col == None` 翻译成 `IS NULL`）。

**⚠️ 派单没点到的 Critical 连带**：`batch_id` 改可空之后，
`schemas/feedback.py` 的 `ClassSessionRead.batch_id: int` 与
`TrainingLogRead.batch_id: int` **必须**跟着改成 `int | None`，否则一条 `NULL`
会让 `response_model` 校验失败 → **500**，而 500 会把「这一行是用户实时写的」
伪装成服务器故障。同理 `ClassSessionCreate.batch_id` 从**必填**改成可选
（Task 3 那段「教师建课次之前库里得先有一次 daily 运行、前端从既有行里读一个
`batch_id` 复用」的别扭口径因此**作废**，docstring 按实际改写）。

### 2.2 ⚠️ 超出派单：给 `training_log` 加 `submitted_at`（`DateTime NOT NULL`、无缺省）

**为什么必须加**：派单的决定 ② 逐字要求「补卡入库但不计入完成率
（`log_date` 与 `submitted_at` 的日期不一致时）」，而 **`training_log` 没有
`submitted_at` 这一列**——读侧无从判断哪一行是补卡。spec §4.5 的字段清单里也漏了它
（只有「日期」），而 spec §8.1 自己要求判 `late`，判 `late` 就需要提交时刻。

**替代方案与为什么不选**：把「补卡」编码进 `late`（补卡也置 `True`）。
**明确不选**——那会把「22:05 交的当天卡」与「三天后补的卡」**不可逆地混成一档**，
而 Task 6/7 的 `YELLOW_CHECKIN_GAP` 与事后审计都可能要区分两者。
信息销毁比多一列贵：本仓不做迁移，**现在**加一列比**以后**加便宜
（以后加 = 重建库 + 历史行的 `submitted_at` 永远只能是 `NULL`）。
⚠️ 加完之后 `training_log` 与 `rpe_record` 也对称了：两张都是「学生实时提交」的表，
此前只有一张有提交时刻，那个不对称本身就是这一列缺失的征兆。

**连带（6 处，全部实测过）**：`training_log` 的形状 10 列 → **11 列**；
`TrainingLogRead` 加同名字段（位置必须与 DB 列序一致，因为
`test_read_models_match_the_db_columns` 按**顺序**逐字对齐）；
`test_the_plan03_tables_inject_the_clock_and_never_default_it` 的 `time_columns`
映射加一格；`app/demo_data.py` 的 `_training_logs` 必须填值（否则 NOT NULL 当场炸）；
`tests/db/test_models.py::_training_log_fields` 与
`tests/api/test_crud.py::_seed_one_row_per_table` 各加一行。
⚠️ `app/demo_data.py` **不在派单的 Modify 清单里**，但这一列让它必须动。

**演示数据的口径决定**（如实记录）：`demo_data` 造的打卡行 `submitted_at` 的**日期取
`log_date`**（即「当天打的卡」），时刻取 20:00（不迟）/ 22:30（迟）。
⚠️ 若按真实的「今天」填，那么演示生成器回填的过去 14 天**每一行都是补卡**，
而补卡不计入完成率 → `weekly_class_report.checkin_rate_by_layer`（Task 9）
在演示库里恒为 **0**，演示就没东西可看了。故按「当天打卡」造，
`DEMO_CHECKIN_HOUR` 那一段注释里逐字声明了这是演示口径。

### 2.3 P5-A3：`TrainingLog.SOURCES` 与它的新 CHECK

| 项 | 实测值 |
|---|---|
| `TrainingLog.SOURCES` | **`{"checkin", "lepao", "demo"}`**（`sorted` → `['checkin', 'demo', 'lepao']`） |
| 新 CHECK 名 | **`ck_training_log_source`** |
| 约束文本（运行时反解） | `source IN ('checkin', 'demo', 'lepao')` |
| 最长值 vs 列宽 | `"checkin"` = 7 ≤ `String(16)`，余量 9 |
| 采集端点写哪个值 | **`"checkin"`**（`routers/feedback.py::CHECKIN_SOURCE`） |

⚠️ **`"demo"` 必须在词表里**（派单只说了「至少 `{"checkin", "lepao"}`」）：
`app/demo_data.py` 的 `DEMO_SOURCE = "demo"` **今天就在写它**，
漏掉的话演示生成器的第一条打卡就当场 `CHECK constraint failed`。
这一条由变异 **M9b** 反证（去掉 `"demo"` → `tests/test_demo_data.py` 红 2 条）。
⚠️ `"lepao"` 今天**生产里没有写入方**（实测 `app/pipeline/daily.py` 一个字节都不往
`training_log` 写；`app/` 下唯一构造 `TrainingLog` 行的生产代码是 `demo_data.py`），
仍放进词表，照 `Notification.CHANNELS` 的既有处置：
「届时往一个已结案的 CHECK 里加值等于重建库（本仓不做迁移）」。

### 2.4 P5-A4：`app/config.py` 的 `TIMEZONE`

| 项 | 实测值 |
|---|---|
| `config.TIMEZONE` | **`"Asia/Shanghai"`** |
| `config.__all__` | `['BACKEND_DIR', 'DEFAULT_CSV_DIR', 'DEFAULT_DB_URL', 'TIMEZONE']`（4 项） |
| `config` 的 import | **仍只有 `pathlib`**（`zoneinfo` 由调用方 import） |

⚠️ 刻意**不在 `config.py` 里构造 `ZoneInfo` 单例**：那会让「时区数据库缺失」这一类
环境故障变成 **import 期**故障（整个 `app` 都导不进来），而放在调用方则只在打卡端点响。
判定式是 `datetime.now(ZoneInfo(TIMEZONE)).replace(tzinfo=None)` ——
⚠️ `.replace(tzinfo=None)` 是**承重的**：库里存 naive，aware 与 naive 相比会当场
`TypeError: can't compare offset-naive and offset-aware datetimes`。

### 2.5 P5-A6：`ClassSession.RPE_TOKEN_LEN`

| 项 | 实测值 |
|---|---|
| `ClassSession` 的类常量 | **`['RPE_TOKEN_LEN']`**（此前是 `[]`） |
| `RPE_TOKEN_LEN` | **16** |
| `rpe_token` 列宽 | **16**（`String(RPE_TOKEN_LEN)`，不再写字面量） |
| 生成式 | `secrets.token_urlsafe(RPE_TOKEN_LEN * 3 // 4)[:RPE_TOKEN_LEN]` |
| 实测生成长度 | **16**（40 次采样，40 个互不相同） |

⚠️ 字节数 `12` 由列宽**派生**（base64url 每 3 字节 → 4 字符），故「16」只有一个住址；
末尾那个切片是**兜底**（SQLite 不强制 `VARCHAR` 长度，溢出在本仓永远不报错，
换到 MySQL 会静默截断、而截断后的口令**永远校验不过**——症状看起来像「学生输错了口令」）。
⚠️ 用 `secrets` 不用 `random`：后者是梅森旋转伪随机，看过几个输出就能预测下一个口令。
⚠️ **架构守卫不拦 `secrets`**（与控制者的预检一致，本 Task 未动守卫）：
`_is_api_allowed` 是只针对 `app.*` 前缀的 allow-list，标准库不受它约束；
且 `API_ALLOWED_PREFIXES` 里已含 `app.api`（层内互相依赖），故本模块
`from app.api.routers.prescription import _current_prescription` 合法。

### 2.6 `repo.delete_by_batch` 的 docstring 同步（硬规矩 #66）

两段：① 写明九张里有**两张**的这一列现在可空、以及为什么（`NULL` 让实时行天然躲过
`WHERE batch_id = :b`），并写明本函数的**契约变窄了一格**（对那两张表它删的是
「这一批同步写进来的那些行」，不是「这张表里属于这一天的所有行」）；
② ⚠️ **原文那句「`TrainingLog` 由 Task 5 接（进 `_replay_cleanup`）」没有兑现**，
按**实际发生的事**改写——留一个不兑现的预告，正是同一段 docstring 自己批评过的
那个形状（它逐字记着「Task 7 早已接完，那句话于是变成了一个已完成动作的预告」）。
没接的三条理由写在原处：管道今天不写这张表（接进去删 **0 行**是死代码，
而「一条删 0 行的清理」会让下一个人以为打卡已被重放管住）；这一列现在可空、
实时行本来就躲过本函数；**谁让管道写 `training_log`，谁负责把它接进
`_replay_cleanup`**（Task 9 或之后）。已登记为关切。

---

## ③ 七个端点：路径 / 方法 / 请求响应形状

| # | 方法 + 路径 | 码 | 身份 | 请求体 | 响应模型 |
|---|---|---|---|---|---|
| 1 | `POST /api/class-sessions/{class_session_id}/open-rpe` | **200** | 教师 | — | `RpeOpenResult`（4 键） |
| 2 | `POST /api/rpe-records` | **201** + `Location` | 学生 | `RpeSubmitCreate`（4 字段） | `RpeRecordRead`（6 列） |
| 3 | `GET /api/class-sessions/{class_session_id}/rpe-status` | **200** | 教师 | — | `RpeStatusRead`（11 键） |
| 4 | `POST /api/training-logs` | **201** + `Location` | 学生 | `TrainingLogCreate`（5 字段） | `TrainingLogRead`（11 列） |
| 5 | `GET /api/students/{student_id}/training-logs/completion-rate?semester_id=&week=` | **200** | 学生 | — | `CompletionRateRead`（12 键） |
| 6 | `POST /api/mini-tests/batch` | **200** | 教师 | `list[MiniTestEntryCreate]`（每项 7 字段） | `MiniTestBatchResult`（2 键） |
| 7 | `GET /api/mini-tests/normalized?semester_id=&week=` | **200** | 教师 | — | `NormalizedScoreRead`（4 键） |

**201 vs 200 的区分**与 Task 3/4 逐字一致：2 与 4 是「创建了一个新资源」（有它自己的
URI 可指，故给 `Location`），1 是「对已存在的课次做了一次操作」、6 是「一次提交若干行、
要回报每一行的下落」（响应体是**报告**、不是一个新资源）。

**服务端填的字段一个都不在请求模型上**（守卫
`test_the_request_models_cannot_carry_the_server_filled_fields`）：
`RpeSubmitCreate` 少 `student_id` / `submitted_at`；`TrainingLogCreate` 少
`student_id` / `submitted_at` / `late` / `source` / `batch_id`；
`MiniTestEntryCreate` 少 `entered_by` / `normalized_score`。
⚠️ 钉的是「字段**不在模型上**」而不是「多传会 422」：Pydantic 缺省 `extra="ignore"`，
多传的键会被**静默丢掉**，故前者才是「服务端那一份不可能被覆盖」的真正保证
（与 Task 4 的 `test_the_override_request_model_cannot_carry_the_two_server_filled_fields`
同一条纪律）。同一条测试**反向**也钉：该由客户端传的字段一个都不能少。

**错误码**（全部经 `app/api/errors.py` 的统一形状 `{"error": {code, message, detail}}`）：

| 情形 | 码 | `code` |
|---|---|---|
| 缺身份头 | 401 | `unauthenticated` |
| 工号/学号不在册、或替别人读写 | 403 | `forbidden` |
| 快评口令不匹配 | **403** | **`invalid_rpe_token`** |
| 课次/学期不存在 | 404 | `not_found` |
| 快评还没被发起 | **409** | **`rpe_not_opened`** |
| 一节课重复交快评 / 同一天重复打卡 / 小测撞唯一键（整条） | 409 | `integrity_conflict` |
| `rpe` 越界 / `feeling` 域外 / 分页参数越界 | 422 | `request_validation_failed` |
| 小测**批量**里的单行失败 | **200** | —（进 `failed` 列表，点名 `index` + `student_id` + DBAPI 原文） |

⚠️ **「快评没发起」用 409 不用 422**：请求体本身没有错，错的是**资源的状态**；
给两个码是为了让前端能区分「你填错了」与「老师还没发起」。
⚠️ 且这一道闸门**必须排在验口令之前**：没发起时 `rpe_token IS NULL`，
先验口令会把「老师还没发起」报成「你口令错了」，而两种提示教师要做的事完全不同。
⚠️ **口令不匹配用 403 不用 404**：与 `require_scope` 同一条口径——区分
「课次不存在」与「口令不对」等于把「哪些课次已经发起了快评」告诉调用方。

**⚠️ include 顺序在本 Task 起承重**（派单没点到，见 §6 顶回 #5）：
`GET /api/mini-tests/normalized` 与泛型工厂为 `mini-tests` 注册的
`GET /api/mini-tests/{mini_test_id}` **完全同形**（两段、末段一个占位），
FastAPI 按注册先后取先匹配的，故 `feedback` **必须**排在 `catalog` 之前；
排反了会得到 **422** 且消息是「`mini_test_id` 不是一个整数」——
那个消息会把下一个人支去修前端传的参、而不是修 include 顺序。
守卫是 `test_the_normalized_route_is_not_swallowed_by_the_generic_read_route`
（它同时验泛型的 `GET /api/mini-tests/{id}` **仍然活着**，即两者共存而不是互斥），
变异 **M6** 反证（顺序反过来 → 该条红）。
⚠️ `routers/__init__.py` 的模块 docstring 里「本包的对策不是靠顺序，而是让那种重叠
不存在」与「include 的顺序今天不承重」两段**都已不成立**，按实际改写：
对策分成「写入侧靠 `writable=False` 让重叠不存在」与「**读取侧只能靠顺序**
（读端点是泛型工厂的核心产出，没有开关可关）」两半，规则定为
「**特例一律 include 在 `catalog` 之前**」——`prescription` 因此一并前移
（它与顺序无关，但一条不需要逐个 router 去做同形分析的规则才是能执行的规则）。

---

## ④ `late` 的三条边界测试 + 完成率的分母口径

### 4.1 Review Focus 第 2 条：三条边界（**只差一秒**）

| 测试 | 冻结时刻 | 期望 `late` |
|---|---|---|
| `test_the_checkin_deadline_is_a_closed_interval_at_22_00[21:59:59]` | `2025-09-03 21:59:59` | **False** |
| `test_the_checkin_deadline_is_a_closed_interval_at_22_00[22:00:00]` | `2025-09-03 22:00:00` | **False**（整点算闭区间内） |
| `test_the_checkin_deadline_is_a_closed_interval_at_22_00[22:00:01]` | `2025-09-03 22:00:01` | **True** |

三个参数化用例同住一个测试函数（`LATE_BOUNDARIES` 那一份清单），
判定式的住址是 `routers/feedback.py::CHECKIN_DEADLINE`（`= dt.time(22, 0)`）
与它那个 **`>`**（不是 `>=`）。⚠️ 变异 **M1** 反证：把 `>` 改成 `>=`
→ **只有中间那条红**（`1 failed, 2 passed`），这正是边界测试该有的形状。

⚠️ **时钟必须可注入**，否则这三条只能在每天 21:59–22:01 那两分钟里跑——
那不是测试，是彩票。`_now_local()` 是「现在几点」在本模块的**唯一住址**，
测试 `monkeypatch` 它一格就换掉全部端点看到的时钟（`_freeze` 助手）。
⚠️ 刻意**不换** `dt.datetime`：那是全仓共用的类，换掉它会连带影响 SQLAlchemy 与
Pydantic 内部对时间的处理。

另外两条口径也各有守卫：
* **② 补卡入库但不计入完成率** —— `test_a_backfilled_checkin_keeps_both_dates_apart`
  （09-05 21:00 补打 09-01 的卡 → 入库、`late=False`（21:00 < 22:00）、两个日期各归各）
  + `test_late_rest_day_and_backfilled_rows_do_not_count`（分子排除它）。
* **③ 一律用 `app.config.TIMEZONE`** —— `_now_local` 的
  `.replace(tzinfo=None)`，且真机冒烟量到 `submitted_at = 2026-10-09T21:09:21`
  与 `late=False`（当时 21:09），两者自洽。

### 4.2 完成率的分母（P5-A2 的落地，⚠️ 与裁定字面有一处偏离）

**实现位置**：`backend/app/api/routers/feedback.py` 的
`completion_rate()`（分母 = `expected` 那个列表）+ 私有助手
`_training_days_of()`（处方周次 → 训练日**日期集合**）+ `_week_days()`（学期周次 → 7 天）。

**口径**：分母 = **处方训练日 ∩ 所查学期周的 7 天**，
即 `len(expected)`；分子 = 那些日子上 `completed 且 not late 且 not is_rest_day
且 submitted_at.date() == log_date`（非补卡）的行数。

⚠️ **裁定说的是「分母改成 `len(sheet.sessions)`」，实现是「取交集」**。
两者在处方周与学期周**对齐时逐字相同**（守卫
`test_the_completion_rate_denominator_is_the_prescription_training_days`：
绿层 2 天 → 分母 2），错位时**交集那一个才对**（守卫
`test_training_days_outside_the_queried_week_do_not_count`：处方 09-04 生成 →
学期第 1 周只数到 09-04/09-05，学期第 2 周只数到 09-11/09-12）。
**取交集同样兑现裁定的理由**（交集的大小随 `sheet.sessions` 变，故教师改周天数、
分母跟着变），并且多做对一件事：`generated_on` 不是学期第一天在真实数据里是**常态**，
那时无条件的 `len(sheet.sessions)` 会把不属于这一周的日子算进分母，
于是「这一周一天都没训」被讲成「分母 2、分子 0 = 0%」。
变异 **M4** 反证（改回无条件 → 那条错位测试红）。

**「分母随教师覆盖变」的核心守卫**：
`test_the_denominator_follows_a_teacher_weekly_frequency_override`
（红层 4 天 → 教师 `WEEKLY_FREQUENCY` 覆盖成 2 → 分母 **2**、完成率 **1.0**；
若读模板值会给出分母 4、完成率 0.5，把一个**依从性最好**的学生报成半个不及格）。
⚠️ **方向是「减」不是「加」**（顶回 #7）：实测
`app/domain/prescription/override.py` 的模块表格逐字写着 `WEEKLY_FREQUENCY` 的效果是
「**保留前 N 课** + 按 N/原课次重量」，故把绿层的 2 天覆盖成 4 天**不会**变成 4 课
（只有 2 课可保留）。派单 P5-A2 举的例子是「教师改了周天数」，
本条按那个覆盖**真的能做到的方向**来钉。

**`null` 的三档**（P5-A2：「不知道」不得讲成「0%」，各有自己的 `reason`）：
① 这一周没有任何一天有生效处方（`prescription_id` 也是 `null`）——
`test_no_prescription_gives_a_null_rate_and_not_zero`；
② 有处方但 `current_week` 返回 `None`（已到期 = spec §5.2 触发 3）——
`test_an_expired_prescription_gives_a_null_rate_and_not_zero`
（⚠️ 造这一档**必须**用 `valid_to=None`：`_current_prescription` 把 NULL 当
「不设终点」放行，于是那张行在第 8 周仍被选中而 `current_week(09-01, 10-20, 4) = 8 > 4`
→ `None`；若把 `valid_to` 填成正常的 09-28，那一周根本找不到处方，
本条就退化成 ① 的重复）；
③ 有处方、周次也算得出，但训练日与这一周**一天都不重叠**。
另有一档**刻意不回 `null`**：`paused=True` 时照样算分母、把 `paused` 单独透出去
（`test_a_paused_week_still_reports_its_denominator`，P8-A3：「暂停」与「本周量为 0」
是两件不同的事，`weekly_training_sheet` 对 `paused` 只抄不判；在后端把它抹成 `null`
或 `0` 都是替前端做了它自己该做的决定）。

**复用而不抄第二份**：「哪一张处方在那一天生效」直接
`from app.api.routers.prescription import _current_prescription`——
完成率端点与学生端「本周训练单」必须对这件事给出**同一个答案**，
否则同一屏上的两个数会互相矛盾。⚠️ 跨 router import 一个私有函数有先例
（Task 4 自己就 `from app.api.crud import _get_or_404`）。

---

## ⑤ `test_models.py` 因本 Task 红掉的断言（硬规矩 #88：跑全量、逐个收进来）

⚠️⚠️ **先顶回派单的一处事实错误**（顶回 #2）：P5-A3 说「加 CHECK 是 schema 变更 →
`test_models.py` 里『`_in_domain` 列数 = **23**』那条**断言**会红」。
**实测没有这样的相等断言**：那一处是
`assert len(domains) >= 10`（**下界**），且它自己的注释逐字写着
「⚠️ 这是**下界**、刻意不逐 Task 抬高：抬到 == 11 会让 Plan 02 剩下的三个 Task
每次都来改这一行，而它抓不到任何新失效」。
**「23」只是 `test_string_column_widths_fit_their_value_domains` docstring 里的散文**，
故加 CHECK **不会让任何断言红**。按硬规矩 #88 跑全量后，真正红掉的是下面这些：

| # | 文件 :: 测试 | 红的原因 | 改成什么 |
|---|---|---|---|
| 1 | `tests/db/test_models.py::test_the_seven_plan03_tables_have_the_documented_shape` | `_PLAN03_TABLE_SHAPE` 钉住 `training_log` 是 `(10 列, 2 约束)`，实到 `(11, 3)` | 改成 **`(11, ["ck_training_log_feeling", "ck_training_log_source", "uq_training_log_student_day"])`**，并在那份清单的注释里写明「Task 2 结案时是 10/2、Task 5 起是 11/3」与两个新增各自的出处；同时补一句「`class_session` 仍是 **7** 列：Task 5 只改了它两列的**可空性**与 `rpe_token` 的宽度来源，列数与约束都不变」 |
| 2 | `tests/api/test_prescription_api.py::test_the_identity_headers_are_registered_as_openapi_security_schemes` | 第 ③ 拍是「除 `expected` 清单外**无** `security`」的**全仓级**断言，而七个新端点都挂了 `Security(...)` | `expected` 从 **4** 项扩到 **11** 项（Task 4 的 4 + Task 5 的 7，按学生侧/教师侧分组并注明），docstring 里写明「这份清单会随每个 Task 增长，Task 7/8/9 每加一个带身份的特例端点都要回来加一行——这是**有意的**：它逼着『哪些端点要身份』有一份可读的全貌」，并如实记下代价（它也会因为「有人给一个 CRUD 资源错挂了 `Security`」而红，而那次的报错会指向**本文件**、不是犯错的那个 router） |

**没有红、但按硬规矩 #66 必须同步的散文（5 处，全部实测过）**：

| # | 位置 | 原文 | 改成 |
|---|---|---|---|
| 3 | `test_string_column_widths_fit_their_value_domains` docstring | 「今天 **23** 列」+ 逐列清单 | 「今天 **24** 列」+ 把 `training_log.source` 从第 2 类（无 CHECK）移到第 1 类，并写明 P5-A3 是兑现那一列注释里「Task 5 落地时必须回来定这个值域并补 CHECK」那句预告 |
| 4 | 同上 | 「Plan 03 的 7 张新表里有 **6** 个 `String(n)` 列没有 CHECK」+ 6 个列名 | 「原有 6 个，**Task 5 之后是 5 个**」+ 删掉 `training_log.source`，并写明「那条字面量测试**仍保留** `source` 的一格（钉『恰好 16』），因为遍历只判**够宽**、不判**不许改窄**」 |
| 5 | `test_the_unconstrained_string_columns_of_the_plan03_tables_are_wide_enough` 的 ④ | `longest_rpe_token = "A3F9K2QX"` / `len == 8`，注释「演示与 Task 5 都用 8 位大写字母数字」 | 字面量改成 **`"aB3-_xY9kL2mNpQr"`** / `len == 16`，注释改成「**两个写入方、两种长度**：演示侧仍是 8 位大写十六进制，而 Task 5 生成的是 base64url、长度**恰好等于列宽**，故最长真实值是 16、余量 0」 |
| 6 | 同上的 ⑥ | `longest_source_today = "demo"` / `len == 4`，注释「今天没有唯一所有者」 | 字面量改成 **`"checkin"`** / `len == 7`，注释改成「值域已有唯一所有者（`SOURCES` + CHECK），本格保留的唯一职责是钉『列宽恰好 16』；字面量从 `"demo"` 更正成 `"checkin"`，否则它还在按旧词表说话」 |
| 7 | `app/demo_data.py` 的 `DEMO_SOURCE` 注释 | 「那一列今天**没有唯一所有者**」 | 「取值域自 Task 5 起有了唯一所有者（`SOURCES` + `ck_training_log_source`），`"demo"` 是它三个值之一、**并且必须留在词表里**」，并写明「这里仍写**字面量**、不读那个类常量：两侧同源的话词表里少了 `"demo"` 也会一起少、断言恒成立（硬规矩 #35）」 |

⚠️ 第 5、6 两处不是「纯散文精度」：它们的**字面量本身就是期望值**
（`assert len(longest_rpe_token) == 8`），而那个字面量在 Task 5 之后**不再是
今天最长的真实值**——留着它就是一条说假话的守卫（它绿，但它量的东西已经不存在了）。
故按「Critical 级一律当场修」处置。

---

## ⑥ 待清扫 / 关切 / 没按派单做的地方 / 顶回控制者的地方

### 6.1 顶回控制者的地方（**8 处**）

| # | 级别 | 顶回什么 | 处置 |
|---|---|---|---|
| **1** | **事实错误** | **P5-A5 说「`deps.Page` 实测是一个函数、不是 Pydantic 模型」（`def Page(*, limit: Annotated[...], offset: Annotated[...]) -> None`）。现场实测 `app/api/deps.py:235` 是 `class Page(BaseModel)`，两个字段是 `Field(default=50, ge=1, le=200)` 与 `Field(default=0, ge=0)`。全仓只有这一份定义（AST/grep 双口径核过：`deps.py` 定义 + `crud.py` 两处使用）。** | 结论不受影响（`page: Page = Depends()` 对 Pydantic 模型同样成立，Task 3 的 23 个资源正在这么用），故**没改 `Page`**。⚠️ 但**本 Task 一个 `Page` 都没用**——七个端点里三个是操作/单行读、两个是按 `semester_id + week` 聚合读、两个是写入，没有一个需要分页。派单把 P5-A5 列为 Important 是为「用对形状」，而实际答案是「用不到」。 |
| **2** | **事实错误** | **P5-A3 说「`test_models.py` 里『`_in_domain` 列数 = 23』那条断言会红」。实测没有这样的相等断言**——那一处是 `assert len(domains) >= 10`（下界，且注释逐字写「刻意不逐 Task 抬高」）。「23」只是 docstring 里的散文。 | 按硬规矩 #88 跑全量，把**真正**红的 2 条收进来（§5 表格的 #1 #2），并按 #66 同步 5 处散文（#3–#7）。⚠️ 派单那句「先跑全量、把红掉的相等断言逐个收进来，不要只 grep 那个数」的**方法**是对的、且正是它让我发现了真实红点与预告的不一致。 |
| **3** | **Critical（连带不全）** | **P5-A1 只说了改两列的可空性与同步 `repo` 的 docstring，没说读模型。** 而 `ClassSessionRead.batch_id: int` / `TrainingLogRead.batch_id: int` / `ClassSessionCreate.batch_id: int`（必填）不改的话，第一条 `NULL` 就让 `response_model` 校验失败 → **500**，而 500 会把「这一行是用户实时写的」伪装成服务器故障；`ClassSessionCreate` 不改则 P5-A1 要解决的「教师实时建课次」**仍然做不到**（前端还是被迫编一个 `batch_id`）。 | 三个模型一并改（`int | None` / `int | None = None`），并把 Task 3 那段「教师建课次之前库里得先有一次 daily 运行」的别扭口径按实际改写。**这是 P5-A1 真正落地的一半**，缺了它那条裁定只解决了一半问题。 |
| **4** | **Critical（缺列）** | **`training_log` 没有 `submitted_at` 列，而派单的决定 ② 逐字用它作判据**（「`log_date` 与 `submitted_at` 的日期不一致时」）。没有它，「补卡不计入完成率」在读侧**无处落地**：`late` 只看时刻，一个 21:00 补打前天卡的学生 `late=False`，与当天打的那一行在库里长得一模一样。 | 加列（`DateTime NOT NULL`、无缺省，时钟由调用方注入，与本包约定一致）。**替代方案（把补卡编码进 `late`）明确不选**：那会不可逆地混掉两档，而信息销毁比多一列贵。连带 6 处全部收进来（§2.2）。⚠️ 这动了 `app/demo_data.py`，它不在派单的 Modify 清单里。 |
| **5** | **Critical（路由冲突）** | **`GET /api/mini-tests/normalized` 与泛型的 `GET /api/mini-tests/{mini_test_id}` 完全同形**，而 `mini-tests` 是只读资源、泛型**注册**了它的 read。派单只说「include 新 router」、没说顺序，而 `routers/__init__.py` 的 docstring 当时逐字写着「include 的顺序**今天不承重**」。照它做会得到 **422** + 「`mini_test_id` 不是一个整数」。 | `feedback` include 在 `catalog` **之前**；`prescription` 一并前移（规则统一成「特例一律在泛型之前」）；`routers/__init__.py` 那两段不成立的 docstring 按实际改写；加守卫 + 变异 M6 反证。⚠️ 读取侧的重叠**没有 `writable=False` 那样的开关可用**（关掉读端点等于关掉整个资源的 read），故只能靠顺序——这条规则要传导给 Task 7/8/9。 |
| **6** | **证据不成立** | **Ruling 12 的理由之一是「全量跑时机器负载会把它推过 60 s（实测 61.58 与 62.72）」，本机 n=2 亲跑是 47.33 / 47.96 s，没有复现**（对 60 的余量 1.25×，即它没有真的红过、只是余量薄）。 | **仍按裁定落 90**（flaky 的诊断成立，只是依据要换成「余量 < 2×」而不是「越界」）。docstring 里如实写「未复现」，**没有**把控制者的两个数写成我亲跑的值（硬规矩 #6）。⚠️ 并给出一个数据点：若只按本机最坏值算，满足 2× 线的阈值是 **96 s** 且仍抓得住 115.08，即**本机 96 严格优于 90**；要抬到 96 请连同控制者那台机器的复测一起做。 |
| **7** | **例子方向错** | **P5-A2 的论证举例是「教师用 `OverrideKind.WEEKLY_FREQUENCY` 覆盖过之后 `sessions` 已经反映了覆盖后的天数」，暗示可以往上调。实测 `override.py` 的模块表格逐字写着它的效果是「**保留前 N 课** + 按 N/原课次重量」——只能减、不能加**（绿层 2 课覆盖成 4 仍是 2 课）。 | 裁定的**结论**不受影响（`len(sheet.sessions)` 确实反映覆盖后的天数，只是方向单边），守卫改成「红层 4 天 → 覆盖成 2 天 → 分母 2」（`test_the_denominator_follows_a_teacher_weekly_frequency_override`），并在 docstring 里写明这个方向限制。**若不核这一步，那条守卫会绿着但什么都没验**（覆盖成 4 之后分母仍是 2，与「读模板值」给出同一个数，两侧同源于失效）。 |
| **8** | **口径偏离** | **完成率的分母实现成「处方训练日 ∩ 所查学期周」，不是裁定字面的 `len(sheet.sessions)`。** | 见 §4.2：取交集**同样兑现裁定的理由**，且处理了处方周与学期周错位（真实数据里的常态）。两者在对齐时逐字相同（各有一条守卫）。**这是本 Task 唯一一处刻意偏离裁定字面的地方**，报出来请控制者裁。 |

⚠️ 累计：Plan 02 顶回 25/25、Plan 03 Task 1–4 顶回 17/17、**本 Task 8 处**
（累计 **50**）。共同点仍是那一条：控制者对着「文档的形状」推理，
实现者对着「守卫实际能抓到什么」推理——本次 #2 #7 两处正是「文档说会红/文档举的例子」
与「跑一遍才知道」的差。

### 6.2 没按派单做的地方（**7 处**，全部是必要的连带或如实报告的偏离）

| # | 偏离 | 为什么 |
|---|---|---|
| 1 | 给 `training_log` 加了 `submitted_at` 列 | 顶回 #4：不加就无法实现派单自己的决定 ② |
| 2 | 动了 `app/demo_data.py`（不在 Modify 清单） | 上一项的必然连带（NOT NULL 列，演示生成器不填就当场炸）；顺带按 #66 同步了 `DEMO_SOURCE` 的注释 |
| 3 | 动了 `tests/api/test_crud.py`（不在 Modify 清单） | 同上（`_seed_one_row_per_table` 手工插一行 `TrainingLog`，必须给新列值） |
| 4 | 动了 `tests/api/test_prescription_api.py`（不在 Modify 清单） | 顶回 #2 的表格 #2：那条 securitySchemes 守卫是全仓级断言，不收进来就红 |
| 5 | 完成率分母取交集（顶回 #8） | 见 §4.2 |
| 6 | 移动了 `prescription` router 的 include 位置（派单只说 include `feedback`） | 顶回 #5：让规则统一成「特例一律在泛型之前」，下一个 Task 不必再做一次同形分析。⚠️ 对 `prescription` 本身**行为无变化**（它的四个路径与泛型不同形），已由 956 passed 验证 |
| 7 | 七个端点**一个都没用** `deps.Page` | 顶回 #1：没有一个端点需要分页（三个是操作/单行读、两个是按 `semester_id + week` 聚合读、两个是写入） |

⚠️ **没有**擅自做的三件事（派单说「不做」就一件都没做）：不做扫码签到；
不做 `rpe_token` 过期；不做真实鉴权（仍走 `X-Student-Id` / `X-Teacher-Staff-No`）。
⚠️ **也没有**跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`
（会写禁区）；完成率测试要的处方是在 python 里用 `assemble()` + 真模板 YAML 现场装配的。

### 6.3 关切（硬规矩 #39：如实记录「守不住什么」）

1. **`rpe_opened` 与 `rpe_token` 的一致性只兑现了一半**：`open_rpe` 端点是
   「两者一起写」的唯一住址，故那个状态从这里出不去；但泛型的
   `PATCH /api/class-sessions/{id}` **仍然**能把两列改成不一致（Task 3 刻意不加跨列校验）。
   要彻底关掉得给 DB 加一条跨列 CHECK，那是改一张已结案的表。
2. **`mini_test.normalized_score` 那一列与 `/normalized` 端点算的不是同一个数**：
   本 Task 让端点**现算不回写**（回写会让一个 `GET` 有副作用），故那一列今天**只有**
   `demo_data` 一个写入方（写的是演示口径的近似值）。`GET /api/mini-tests` 读到的是
   那一列、`GET /api/mini-tests/normalized` 读到的是现算值，**两者可以不同**。
   ⚠️ 前端要用哪一个必须写死在对接文档里。
3. **`mini-tests/batch` 全部失败也回 200**（派单逐字要求的形状），故前端**必须**读
   `failed` 的长度、不能只看状态码。
4. **教师侧四个端点没有「教师 ↔ 班级 ↔ 学生」授权模型**：任何在册教师可以读任何班的
   已交/未交名单、录任何班的小测（`require_teacher` 的 docstring 里已记这条代价，
   本 Task 继承它，没有 worsen 也没有改善）。
5. **打卡端点不校验 `log_date` 落在学期内**：真机冒烟时系统日期是 `2026-10-09`、
   而学期是 `2025-09-01..2025-12-22`，那一行照常入库（`late=False`）。
   原型口径下这是可接受的（学生打错日期不该被 409 拒），但完成率端点按学期周取数，
   故那一行**永远不会**被任何一次完成率查询看到——它只是躺在库里。
6. **`PROXY_FILL_SECONDS = 60` 是本 Task 定的工程决定**：spec §8.1 只说「指导文件要求
   **10 秒**内完成」，10 秒太紧（网络慢、字体大、读题慢都会超），故取 6 倍作为
   「明显不是在课堂上顺手填完」的粗筛线。**要登记 spec §14。**
7. **`late` 只看时刻、不处理跨时区学生**（`config.TIMEZONE` 的注释里逐字写了）：
   一个在别的时区的学生会被按本时区的 22:00 判迟。要支持就得给 `training_log`
   再加一列存学生的时区。
8. **`rpe_token` 不做过期**：一节课的长度不固定（连堂、拖堂、补课），
   而过期的口令在课堂上表现为「学生明明填对了却报错」。
9. ⚠️ **架构守卫会 AST 解析工作树里的全部 `.py`，包括未入库的 `t5_probes/`**：
   本 Task 第一版验收探针里有一句 f-string 含反斜杠（`f"...{raw.count(b'\r\n')}"`），
   当场让 `test_absolute_folding_matches_resolve_name` 红 **2 条**
   （`SyntaxError: f-string expression part cannot include a backslash`）。
   **这条对控制者也成立**：`t5_probes/_preflight.py` 与 `_preflight2.py` 同样在扫描范围内，
   探针写坏会让全量跑红在架构守卫上、而报错指向 `test_layering.py`，离真因很远。
   ⚠️ 已修（改成 `bytes([13, 10])`）。
10. **schema 变更 ⇒ 既有磁盘库必须重建**：`training_log` 加了 `submitted_at NOT NULL`，
    而 `init_db` 走 `create_all`、对已存在的表**原样跳过**。故控制者那个跑在
    `127.0.0.1:8000` 的 uvicorn 所用的 `pe_demo.db` **必须删掉重建**，
    否则 `POST /api/training-logs` 会撞「表里没有这一列」而 500。
    ⚠️ 本 Task **没有碰** `pe_demo.db`（冒烟一律用 TEMP 库），故那一步留给控制者。

### 6.4 待清扫（**4 条**，全是散文/口径类，无 Critical）

1. `app/api/schemas/feedback.py` 的模块 docstring 那张资源表里，
   「三个只读资源各有自己的特例写入口（**Task 5**）」的措辞可以改成
   「（:mod:`app.api.routers.feedback`，已落地）」——指向一个**已完成的 Task 序号**
   与指向一个**模块**，前者会随计划推进变成历史名词。
   ⚠️ 同一文件里 `ClassSessionCreate` 的 docstring 本 Task 已经这样改过一处。
2. `models/feedback.py` 的模块 docstring 顶部那张表里，`alert` 那一行仍写
   「管道（**Task 7** 的 `alert_stage`）」、`notification` 写「**Task 8** 的 `InAppChannel`」、
   `weekly_class_report` 写「管道（**Task 9** 的 `report_stage`）」——三条都是**未完成的预告**，
   而那正是 `repo.delete_by_batch` docstring 里被批评过的形状。⚠️ 本 Task 只把自己那两行
   （`class_session` / `training_log`）改成了实际口径，另三行留给 Task 7/8/9 各自结案时改
   （**谁兑现谁改写**，替别人改写会变成第二处需要同步的散文）。
3. `_shuttle_percentile` 的 `n = 1` 那一档给 **50.0**（标准 percentile rank 公式的自洽结果），
   而真机冒烟正好量到它（单人班 → `shuttle_score = 50.0`、`composite = 40.0`）。
   ⚠️ 这个 50 **看起来像真的排过名**。原型阶段可接受（单人班的「班内百分位」本来
   就没有意义，而任何返回值都是编的），但前端若把它渲染成「本班前 50%」就是一句假话。
   建议 Plan 04 的学生端在 `scored_count == 1` 时显示「本班仅 1 人参与，无排名」。
4. 本 Task 的 4 个工程决定要登记 **spec §14**：① `training_log.submitted_at` 那一列
   （spec §4.5 的字段清单没有它）；② 补卡不计入完成率；③ `PROXY_FILL_SECONDS = 60`；
   ④ 完成率的分母 = 处方训练日 ∩ 学期周（以及小测综合分的量纲混合）。
   ⚠️ 派单说 spec §14 的登记归 Task 9 结案，故本处只列清单、**没有**动 spec 文件。

---

## ⑦ 最终验收

| 项 | 基线 | 结案 | 判据 |
|---|---|---|---|
| `python -m pytest -q` | 910 passed | **956 passed** / 135.94 s | +46（本 Task 新增），**零退步** |
| `--cov=app.domain --cov-branch` | 996 / 0 / 288 / 0 / 100% | **996 / 0 / 288 / 0 / 100%** | **四格逐字不变** ✅（本 Task 不加 domain 代码） |
| 带 `--cov` 时的通过/跳过 | 909 passed, 1 skipped | **955 passed, 1 skipped** | 那 1 条 skip 就是 Ruling 12 的哨兵（带 cov 时按 `sys.gettrace()` 分支跳过） |
| 表数 | 25 | **25** | 未加表（只给 `training_log` 加了 1 列） |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33** | 运行时口径 = `dir()` 的 39 − 6 个子模块名（§1.2） |
| 扫描面（`SCANNED_DIRS` 四个目录的 `.py` 数） | 50 | **51** | pipeline 8 + db 11 + domain 16 + **api 16**（+1 = `routers/feedback.py`） |
| `/api/` 路径模板 | 51 | **56** | +5（`open-rpe` / `rpe-status` / `completion-rate` / `mini-tests/batch` / `mini-tests/normalized`；另两个端点复用既有的 `/api/rpe-records` 与 `/api/training-logs` 路径，只加方法） |
| `/api/` 操作数 | 77 | **84** | +7（七个端点各一个操作） |
| 三个指纹 | `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` | **逐字不变**（三个都 `True`） | 口径 = `sha256(read_bytes().replace(CRLF, LF))[:16].upper()`，与本仓既有 `_fingerprint` 逐字同 |
| `git diff acd3f53 HEAD -- backend/data` | — | **为空** | 见下方 §7.2 |
| `backend/pe.db` | 不存在 | **不存在** | 全程未跑 `app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily` |
| `backend/data/seed/` | 0 文件 | **0 文件**（目录存在、文件数 0） | |
| `backend/data/**` 行尾 | 全 LF | **23 个文件 crlf 全为 0** | `read_bytes()` 口径（硬规矩 #89 扩写） |

### 7.1 变异自证：**11 / 11 RED**（探针 `t5_probes/mutation_probe.py`）

Ruling 1 说变异只在 Task 6 要求，但 Task 2/3/4 的实现者都自己加了、控制者三次都采纳，
故本 Task 照做。⚠️ 纪律：备份原**字节**到 TEMP、`try/finally` + `write_bytes` 还原
（**绝不用 `git checkout`**，硬规矩 #46）；替换前断言锚点**恰好出现 1 次**
（否则记 `INVALID` 而不是静默跳过）；⚠️ 并且区分「测试红了」与「文件语法坏了」——
后者是**假 RED**（collection error 也返回非 0），记 `ERROR(!!)`。
收尾复核「还原逐字节相同」✅。

| 变异 | 改坏什么 | 该红的守卫 | 结果 |
|---|---|---|---|
| M1 | `late` 的 `>` → `>=`（闭区间变半开） | `…_closed_interval_at_22_00` | **RED**（`1 failed, 2 passed`：只有 22:00:00 那条红）|
| M2 | 完成率分子不再排除 `late` | `test_late_rest_day_and_backfilled_rows_do_not_count` | **RED** |
| M3 | 完成率分子不再排除补卡 | 同上 | **RED** |
| M4 | 分母改成无条件（不取与学期周的交集） | `test_training_days_outside_the_queried_week_do_not_count` | **RED** |
| M5 | 折返百分位方向反（数比自己**快**的人） | `test_squat_score_is_the_count_and_shuttle_score_is_the_within_section_percentile` | **RED** |
| M6 | include 顺序反过来（泛型在特例之前） | `test_the_normalized_route_is_not_swallowed_by_the_generic_read_route` | **RED** |
| M7 | `open-rpe` 每次都换口令（幂等被破坏） | `test_open_rpe_twice_keeps_the_first_token` | **RED** |
| M8 | 综合分把缺失的一项当 0 | `test_a_null_shuttle_time_stays_out_of_the_percentile_and_gets_a_null_score` | **RED** |
| M9 | `SOURCES` 去掉 `"demo"` | `test_the_source_check_rejects_a_value_outside_the_pinned_domain`（DDL 文本） | **RED** |
| M9b | 同上，看**后果** | `tests/test_demo_data.py`（演示生成器当场 CHECK 失败） | **RED**（`2 failed`） |
| M10 | 没人交时 `mean_rpe` 返回 `0.0` 而不是 `None` | `test_rpe_status_lists_who_has_not_submitted` | **RED** |

⚠️ M9 与 M9b 是**同一个变异的两个守卫**：前者钉 DDL 文本（值域的所有者说对了），
后者钉**后果**（少一个值会让演示生成器当场炸）。两条都红才算「词表里有 `demo`」
这件事真的被守住了。

### 7.2 真机端到端冒烟：**28 / 28 全绿**（探针 `t5_probes/smoke_probe.py`）

⚠️ TestClient 用的是**内存库 + StaticPool**，故本项补的是
「**真 uvicorn 进程** + **真磁盘 SQLite 文件** + **lifespan 建表**」这一档。
库文件放 TEMP（`PE_DB_URL` 显式注入，因为 `DEFAULT_DB_URL` 指向禁区 `pe.db`），
端口 **8123**（避开控制者跑在 8000 的那个进程），全程**未碰** `pe.db` / `pe_demo.db` /
`backend/data/` 的任何文件。

按 spec §8.1 的真实使用顺序串一遍，实测值（节选）：

```
openapi：/api/ 路径模板 56 ✅、操作数 84 ✅、securitySchemes 恰好两格 ✅
磁盘库表数 25 ✅
① POST /api/class-sessions（不传 batch_id）→ 201，batch_id = null ✅（P5-A1）
② POST open-rpe → 200，rpe_token = "-mrpy9AAghBkppfZ"（16 字符 ✅）
   再点一次 → 同口令 + already_open=true ✅（幂等）
③ POST /api/rpe-records → 201，Location = /api/rpe-records/1 ✅，
   submitted_at = "2026-10-09T21:09:21.144656"（服务端时钟、naive ✅）
   重复提交 → 409 ✅；错口令 → 403 + invalid_rpe_token ✅
④ GET rpe-status → 200，enrolled_count=1 / submitted 1 / not_submitted [] / mean_rpe 7.0 ✅
⑤ POST /api/training-logs → 201，source="checkin" / batch_id=null / late=false
   （当时 21:09:21 < 22:00，与判定式自洽 ✅）；同一天重复 → 409 ✅；
   feeling="轻松" → 422 + request_validation_failed（**不是** 409）✅
⑥ GET completion-rate → 200，无处方 → completion_rate = null 且 reason 非空 ✅；
   X-Student-Id: 999999 → 403 ✅
⑦ POST mini-tests/batch（2 行，第 2 行撞唯一键）→ 200，
   {"created": 1, "failed": [{"index": 1, "student_id": 1,
    "message": "UNIQUE constraint failed: mini_test.student_id, …"}]} ✅
   ⚠️ message 是 **DBAPI 原文**、不含 SQL 语句与绑定参数（与 errors.py 同一条纪律）
   GET mini-tests/normalized → **200**（不被泛型 read 抢走 ✅），
   单样本 → shuttle_score 50.0 / composite 40.0 ✅
   泛型 GET /api/mini-tests/1 → 仍 200 ✅（两个路由共存）
```

⚠️ 脚本的**清理阶段**撞了一次 `PermissionError: [WinError 32]`（uvicorn 已 terminate，
但 Windows 上文件句柄尚未释放），故 TEMP 里留下了 `t5_smoke.db`（249 856 B）。
**它不在仓库里、不影响任何验收项**，且 28 项检查在那之前已全部完成并打印。
如实记录，不掩盖。

### 7.3 禁区复核

```
git diff acd3f53 HEAD --stat -- backend/data   →  (空输出)
backend/pe.db                                   →  不存在
backend/data/seed/                              →  存在，文件数 0
backend/data/** 23 个文件                        →  crlf 计数全为 0
三个指纹                                        →  逐字不变（3/3 True）
```

⚠️ 全程**没有**执行 `git checkout` / `git switch` / `git merge`（硬规矩 #46：
它们会按 `core.autocrlf` 重写工作树）。`git add` 一律**按文件名逐个加**
（三次 commit 共 15 个文件，无一次 `git add -A`）；`t5_probes/` 始终 untracked、
**未入库**（与控制者的 `_preflight.py` 同一个处置）。
⚠️ commit 时 git 报了 5 次 `LF will be replaced by CRLF` 警告（`core.autocrlf` 的既有行为，
只影响工作树字节、不影响 index/HEAD 的 blob），故 §7.3 的三个指纹与 `data/` 的 diff
是在**commit 之后**用 `read_bytes()` 复核的，两者都干净。

---

## ⑧ commit

| sha | 一句话 |
|---|---|
| **`d933bac`** | Ruling 12：回放耗时那条断言 60 s → **90 s**、函数名改 `under_90_seconds`、docstring 按「数量级哨兵」重写；连带同步 `backfill.py` / `daily.py` 里两处旧函数名与旧阈值（**第一件事**，让「全量绿」恢复可信） |
| **`c8f77cc`** | P5-A1/A3/A4/A6 的 schema 变更：两张表 `batch_id` 可空 + 三个读/写模型跟着改可空、`training_log` 加 `submitted_at`、`SOURCES` + `ck_training_log_source`、`config.TIMEZONE`、`ClassSession.RPE_TOKEN_LEN`；`repo.delete_by_batch` 与 5 处会变成谎话的散文同步；`test_models.py` 红掉的 1 条收进来 |
| **`3be0bc1`** | 七个端点 + 46 条测试（`routers/feedback.py` / `tests/api/test_feedback.py` 新建，`schemas/feedback.py` 补 13 个特例模型，`routers/__init__.py` 的 include 顺序变承重并按实际改写 docstring，`test_prescription_api.py` 的 securitySchemes 清单 4 → 11 项） |
| **`__HEAD__`** | 收尾：结案报告（本文件） |

⚠️ **未 push**（派单要求）。分支仍是 `feature/plan-03-feedback-alert-crud-api`，
**没有**切分支、**没有**碰 `main`。
