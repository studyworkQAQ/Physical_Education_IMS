"""Task 9 落地脚本 10：给 task-9-report.md 追加第 ⑥–⑨ 节（w09 写前 5 节，本脚本 append）。"""
import hashlib
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
TARGET = HERE.parent / "task-9-report.md"

BLOCKS: list[str] = []

BLOCKS.append("""## ⑥ 19 条勘误逐条落地位置

图例：**【改】** = 当场改了代码/测试/夹具；**【写明】** = 按裁定只把口径写进 docstring / spec，不改行为；**【Plan 04】** = 移交。

### A 组 · 事实错误（12 条，全部 Critical，全部当场修）

| # | 勘误 | 落地位置 | 处置 |
|---|---|---|---|
| **1** | `app/domain/alerts.py` 的 `AlertRules.version` docstring 说「Task 7 把它写进 `weekly_adjustment` 的 `auto` 来源留痕」是**错的** | `app/domain/alerts.py`（`AlertRules` 的类 docstring） | **【改】** 改成 `alert.trigger_snapshot["alert_rules_version"]`，并把 Task 7 顶回 4 的推理逐字写下：`reason` 是 `UniqueConstraint("prescription_id","week","reason","source")` 的一列，拼进版本号等于「升一次版本号 = 同一周可以再减一次量」→ `0.64`；`trigger_snapshot` 是 `JsonText`、**不进去重键**，故版本号落那里既可离线复核又不影响去重。并点名写入点是 `evaluate_alerts` 里 `_persist` 的 `snapshot = {**hit.snapshot, "alert_rules_version": rules.version, **extra}`（**亲验过那一行**）。同一条也写进 spec §8.4 的新勘误 |
| **2** | 计划的 P5-A5 说 `deps.Page` 是一个 FastAPI 依赖函数——那句「更正」本身是错的 | spec §14 无新编号；**报告本节** + `app/api/deps.py` 现状核实 | **【写明】** 亲验：`app/api/deps.py` 的 `Page` 是 `class Page(BaseModel)`（`limit: int = Field(default=50, ge=1, le=200)`、`offset: int = Field(default=0, ge=0)`），用法是 `page: Page = Depends()`。**Task 1 的 Interfaces 原文 `Page(BaseModel)` 是对的**。控制者的探针用 `callable()` 挑「函数」，而 Pydantic 模型类也是 callable，故打出了它 `__init__` 的签名（硬规矩 #107 的那个形状：用谓词挑对象时先对一个已知反例验证谓词）。⚠️ **代码一个字没改**——改的话就是把对的改成错的；本条的处置是「在 spec 勘误里写明这件事，免得下一个人照 P5-A5 改」。⚠️ 而 spec 里**没有**一处印着 P5-A5 那句话（它是计划正文的），故落地位置是本报告 + 计划账本，不是 spec |
| **3** | `repo.py::delete_by_batch` 的 docstring 两处过期计数 | `app/db/repo.py` | **【改】** 「清的是九张里的**五张**」→ **七张**（并逐张点名：Plan 01 三张派生表 + Plan 02 的 `prescription` / `weekly_adjustment` + Plan 03 Task 7 的 `alert` + Task 8 的 `weekly_class_report`）；「`Alert` 由 **Task 8** 接进」→ **Task 7** |
| **4** | `prescription_stage.py` 的「`auto` 也留给 Plan 03」与「生产写入方今天仍为零」 | `app/pipeline/prescription_stage.py`（模块 docstring 的 `weekly_adjustment.batch_id` 那一节） | **【改】** 两句都已过期：`auto` 由 **Task 7** 落地（`alert_stage._write_auto_adjustment`，红色预警落库的同一批里就自动写、不等教师点击）、`teacher` 由 **Task 4** 落地（`POST …/overrides` 的 `VOLUME_SCALE` / `PAUSE`）。⚠️ 顺带改了同一节里另一句过期的话：「`weekly_factors_of` 今天在生产路径上**没有调用方**、那张表也**没有数据**」——今天它有**两个**生产调用方（学生端与教师端的 weekly-sheet，共用 `_weekly_sheet_response`），演示库实测 **11 行** `source="auto"` |
| **5** | `app/db/models/feedback.py` 的模块 docstring 与 `Alert.batch_id` / `Notification.alert_id` 的列注释里那些「Task 8」预告 | `app/db/models/feedback.py`（**8 处**）+ `tests/db/test_models.py`（**3 处**） | **【改】** 谁兑现谁改写：模块 docstring 的写入方表（`notification` 那一行改成「`InAppChannel`（Task 7 建、Task 8 加『已读』端点）」、`weekly_class_report` 改成 Task 8）、「传导给 Task 8」两处补「**已兑现**」、「Task 8 可以照常接进清单」改成「Task 7 与 Task 8 已经照常把它们接进」、`Alert.batch_id` / `Notification.alert_id` / `Notification.prescription_id` / `WeeklyClassReport.batch_id` 四处列注释、以及测试侧的两处「Task 8 会把 `Alert` 接进/加进」 |
| **6** | `session.py` 的「15 张表」与 `repo.py::upsert` 的「对 14 个模型通用」 | `app/db/session.py`（**3 处**）、`app/db/repo.py`（1 处） | **【改】** 一律 **25**（运行时口径 `len(Base.metadata.tables)` 实测），并在 `Base` 的 docstring 里给出递增轨迹 15 → 18 → 25 |
| **7** | `refdata_prescription.py::equivalence()` 说「本模块公有函数是 5 个」 | `app/refdata_prescription.py` | **【改】** AST 实测 **8** 个（`ast.parse` 本文件、数 `tree.body` 里的 `FunctionDef` 且名字不以下划线开头）= 那 4 个加载侧 + `sync_exercises` + `load_templates` + `templates` + `sync_templates`；后三个是 Plan 02 Task 3 建模板那一半时加的、加的时候没回来改这一句。⚠️ 并写明「fix round 3 补主语那一次的处置**仍然对**，只是它写下的那个实测值绑错了时点」 |
| **8** | `test_prescription_templates.py` 说行号索引的实现在 `app.refdata_prescription._line_index` | `tests/domain/test_prescription_templates.py` | **【改】** 实现今天住在 **`app/refdata_yaml.py`** 的 `line_index`（Task 6 抽的公共模块），`app.refdata_prescription._line_index` 只是**一个别名**（`_line_index = refdata_yaml.line_index`，由 `test_line_index_is_the_same_object_in_every_consumer` 用 `is` 钉住身份）。⚠️ 并写明失效形态：照原句去改「行号索引」的人会改到**一行赋值语句**上 |
| **9** | `refdata_prescription.py` 的模块 docstring「两段的报错口径刻意不同」那段没指向 `app/refdata_yaml` | `app/refdata_prescription.py` | **【改】** 补上「这两段**今天都由 `app.refdata_yaml` 实现**（Task 6 抽的 6 个通用助手），本模块只留 5 个薄适配器 + 一个 `_line_index` 别名，故下面讲的『口径』是那个公共模块的口径、由本模块与 `app.refdata_alerts` 两个消费者共用」 |
| **10** | `test_layering.py` 里 `>= 40` / `>= 16` 两条断言的注释实测值已陈旧 | `tests/architecture/test_layering.py` | **【改注释、不改断言】** 断言一个字未动（它们在 `test_domain_purity.py` 里各有一份镜像，只改一边破坏硬规矩 #51）。改法是把「69 / 18」**绑到时点**（Plan 02 Task 4 落地时实测）并**另给当前值**：`backend/**/*.py` = **130**（app 82 + tests 47 + scripts 1）、全仓相对导入 = **38**（命令一并给出）。⚠️ 并写明「**不要把下界改成当前值**」——贴死会让一次合法重构变红。⚠️ 控制者给的当前值是 90 / 36，我实测 **130 / 38**；差额的成因见第 ⑦ 节的顶回 5 |
| **11** | `subject_key` 的宽度口径：报告写「`course_section:2147483647` 是 **27** 字符、超宽 **3**」 | `app/domain/alerts.py`（`SUBJECT_PREFIX_SECTION` 的注释） | **【改】** 实测 `len("course_section:") == 15` + `len("2147483647") == 10` = **25** 字符，列宽 `String(24)`，故**超宽 1**（`section:2147483647` = 18 字符、余量 6 不变）。⚠️ **结论不变、前缀仍必须是 `section`**：超宽 1 与超宽 3 在 SQLite 上都不报错（它不强制 `VARCHAR` 长度），换到 MySQL 会**静默截断**，而截断后的 `subject_key` 会让去重键指向另一个主语。**代码是对的，只有那两个数错了**——同一条也写进 spec §4.6 的勘误 |
| **12** | `require_teacher` / `require_scope` 的 docstring 里「原型没有教师↔班级↔学生授权模型」那两句 | 核实结果：`app/api/deps.py` **如实、不用改**；过期的是 `app/api/routers/feedback.py` **指向它们的那一句交叉引用** | **【改】** 逐字核过 `deps.py` 两处：`require_scope` 的末段写着「自 Plan 03 Task 8 起，教师端**读一个具体的班或学生**还要过 `require_teaches_section` / `require_teaches_student`（任教关系），故『教师端一律跨学生』这句话已经不成立了——它今天只 against 那三个**写入**端点还成立」；`require_teacher` 的 ⚠️ 段写着「那个模型 **Plan 03 Task 8 已经把它建出来了**……但**只挂在读的一侧**」。**两句都如实。** 而 `feedback.py` 的模块 docstring 仍写「原型**没有**『教师 ↔ 班级 ↔ 学生』的授权模型（`require_teacher` 的 docstring 里如实记了这条代价）」——它指向的那句话**已经不在** `require_teacher` 里了，故改的是这一侧（并逐条列出今天仍只过在册闸门的**七个**写入端点：本模块四个 + `POST …/overrides` + `POST …/regenerate` + `POST …/alerts/{id}/handle`） |

### B 组 · 口径要写明（5 条）

| # | 勘误 | 落地位置 | 处置 |
|---|---|---|---|
| **13** | 两个不同的 `skipped` 同名不同义 | `app/pipeline/alert_stage.py`（`AlertReport.skipped`）+ `app/pipeline/report_stage.py`（`ReportSummary.skipped`） | **【写明】** 两侧 docstring 各加一段**交叉引用**：`AlertReport.skipped` 是 `dict` = `{rule_id: 「求值过、但判不了」的次数}`（Task 7），`ReportSummary.skipped` 是 `int` = **名册为空的班数**（Task 8）。两格都叫 `skipped` 是因为它们各自回答「这一次跑**跳过**了什么」，而两个阶段跳过的是不同种类的东西；⚠️ 合并成一个名字会让下一个人以为两者可以相加。按硬规矩 #113 的形状写（两处用同一个词，先问「它们回答的是同一个问题吗」） |
| **14** | `daily_sync_run` 三个阶段的可观测量不一致（`prescription_count` / `alert_count` 都有列，周报份数只有日志） | `app/pipeline/report_stage.py`（`ReportSummary` 的 docstring 新增一节）+ `app/api/schemas/pipeline.py`（`RunDailyResult` 的 docstring） | **【写明，不加列】** 按裁定**不加 `report_count` 列**，改为写明这个不对称是**有意的** + 两条理由：① 加列是一次 schema 变更，而本仓**不做迁移**（`create_all` 对已存在的表原样跳过，旧库不会补新列 → 端点在离真因很远处 500，Task 2 撞过），且会连带 `_BATCH_OWNED_TABLES` 之外的多处断言（`test_models.py` 的列清单、`test_main.py` 的 `tables == 25`、`RunDailyResult` 的投影与它那条「19 列一个都不漏」的守卫）；② **收益只是「三个阶段对称」，而对称不是一条需求**——操作员要的「今天生成不生成」已由 `run_daily` 的 CLI 输出单独占一行给出，要**份数**的话 `weekly_class_report` 表本身就是权威，而它比一个计数列更强（计数列只说「写了多少行」，表还能说出「是哪几个班」） |
| **15** | `YELLOW_CHECKIN_GAP` 只对「本周有训练单」的学生可判 | **spec §8.2 的新勘误**（+ `app/pipeline/alert_stage.py` 既有 docstring 核实为如实） | **【写明】** spec 那一格逐字写了**两层收窄**：① 求值人群 = 「本学期在三源里留过痕的学生」，而其中 `training_log` 那一份**只按学期起点收窄、不按 3 周回看窗口收窄**（用同一个窗口的话会漏掉最该被提醒的那一类人：一个连续失联 4 周的学生在那 3 周里一行 `training_log` 都没有 → 不在人群里 → 本规则对他**永远不触发**）；② 可判性 = 本周有生效处方（否则「应打卡训练日」这个基线无从算起 → 中断天数记 `None` 而不是 `0`）。⚠️ 代价一并写明：一个刚转进来、还没被任何一源采集到的学生，即使真的一天都没练也不会收到补练提醒——**这是「宁可不报，也不要报一个没有依据的数」那一侧的错** |
| **16** | `test_the_replay_cleanup_list_is_pinned_to_seven_tables` 的函数名里有「seven」 | 核实：**本 Task 没有加表**（表数仍 25） | **【不改】** 派单的条件是「若本 Task 再加表，连函数名一起改」。表数没变，故函数名与那条断言都**不动**（已核实它仍在 `tests/pipeline/test_report_stage.py:475`，且全量绿） |
| **17** | 预警阈值个数是 **9** 个不是 8 个 | `app/refdata_alerts.py`、`tests/test_refdata_alerts.py`（**2 处**）、`tests/domain/test_alerts.py`、**spec §8.2 的新勘误** | **【改】** 用 PyYAML 现读 `data/alert_rules.yaml` 实测：`RED_MINITEST_DROP` 3（`consecutive` / `drop_pct` / `points_needed`）+ `RED_RPE_SUSTAINED` 2（`rpe_min` / `streak`）+ `YELLOW_CHECKIN_GAP` 1（`gap_days`）+ `YELLOW_CLASS_RPE_HIGH` 1（`mean_rpe_max`）+ `GREEN_MASTERY` 2（`completion_rate_min` / `improve_pct`）= **9**。四处代码/测试一律改成 9 并写出逐条分解；spec 那一格另写明「计划正文与派单一路写 8、**那个数对不上任何一条口径**（既不是规则数 5、也不是参数数 9）」。⚠️ 同时写明**另有两个阈值在 domain 里不被读**（`rpe_min` 与 `improve_pct`：算 streak 与 improved 的是 `alert_stage`，domain 拿到的是已经算好的量），但它们仍原样进 `trigger_snapshot`，故不是死配置 |

### C 组 · 归 Plan 04（2 条，本 Task 只写明）

| # | 勘误 | 落地位置 | 处置 |
|---|---|---|---|
| **18** | 单人班的百分位给 50.0 看起来像真排过名 | `app/domain/report.py::shuttle_percentile` 的 docstring + `tests/domain/test_report.py::test_a_single_person_sample_is_fifty_not_zero_and_not_a_hundred` 的 docstring | **【Plan 04】** Plan 04 应在 `scored_count == 1` 时显示「无排名」。⚠️ **本函数刻意不改**：50.0 是标准 percentile rank 公式的自洽结果，而「什么时候不该显示一个数」是**展示层**的口径——`scored_count` 已经由 `GET /api/mini-tests/normalized` 的响应给出去了，前端有判断依据 |
| **19** | 五条移交项 | 逐条见下 | **【Plan 04】** |

**#19 的五条逐条落地位置**：

1. **教师侧「通知已读」今天没有端点** —— `POST /api/notifications/{id}/read` 挂的是 `X-Student-Id` + 「收件人本人」判据（`recipient_kind == "student"` ∧ `recipient_id == 请求者`，且融进那一次查询）。⚠️ 于是班级级预警推给**教师**的那一条消息（`_notify` 的第三档，真机实测确实存在：`recipient_kind='teacher'`、`title='课堂 RPE 均值偏高'`）**永远无法被标已读**，教师端的红点消不掉。→ 本报告 + 第 ⑦ 节待清扫（**本 Task 未做**：加它要给 `notification` 引入「教师收件人」的作用域判据，而 `require_teaches_section` 需要的是 `course_section_id`、那一列在 `notification` 上没有）
2. **三个写入端点仍只过 `require_teacher`** —— `app/api/deps.py::require_teacher` 的 docstring **已写明**（Task 8 写的，本 Task 逐字核过），本 Task 又补了 `app/api/routers/feedback.py` 那一侧的过期交叉引用（#12）。⚠️ 收窄是一次一行的改动（`require_teacher` → `require_teaches_student`），但会改掉 Plan 04 教师端的可点范围
3. **两档 404 的形状在 OpenAPI 里看不见** —— `no_active_prescription` 与 `outside_microcycle` 都由 `error_response(404, code, …)` 直接造 `JSONResponse`，而 FastAPI 对「返回一个 `Response` 实例」的端点**跳过** `response_model` 校验，故 `/openapi.json` 里那两档的 `code` 与 `detail` 文案一个都看不见（前端只能读代码或撞一次）。→ 本报告 + 第 ⑦ 节待清扫
4. **`_stratification_payload` 是 `input_snapshot_of` 的逆运算，两个所有者（一正一逆）** —— `app/api/routers/dashboard.py` 的 docstring **已写明**（Task 8 写的，本 Task 核过：「⚠️ **它是 `app.pipeline.run_stratify.input_snapshot_of` 的逆运算**」）。⚠️ 漂移形态是具体的：正向那一份加一个键而逆向没跟上，大屏的「分层依据」就少一行，而两侧各自的测试都还是绿的
5. **`refdata_alerts.py` 的 `_as_optional_text` 今天没有调用者** —— 该函数的 docstring **已写明保留理由**（本 Task 核过）。⚠️ 它是 5 个薄适配器之一，删掉它会让「6 个通用助手 ↔ 5 个适配器」那张对账表少一格，而 `tests/test_refdata_alerts.py` 的 AST 守卫钉的正是「5 个适配器名」那个字面清单

---

## ⑦ 待清扫 / 关切 / 没按派单做的地方 / 顶回控制者的地方

### 顶回控制者（**6 处**）

Ruling 5 说「控制者对着『文档的形状』推理，实现者对着『守卫实际能抓到什么』推理，你在代码现场，你的判断优先」。逐条：

1. **`golden_cases.json` 不在 `backend/data/` 下**（派单第 7 节与第 9 节各说了一次）。派单写「GC14 要改 `backend/data/golden_cases.json`」「`git diff cf9ad7a HEAD -- backend/data` 应只多出 `golden_cases.json` 的改动」。实测：`Glob **/golden_cases.json` 全仓**只命中 `backend/tests/fixtures/golden_cases.json`**（`tests/integration/test_golden_cases.py:26` 的 `GOLDEN` 常量也指着那里），而 `git diff --stat cf9ad7a HEAD -- backend/data` 是**空的**。⚠️ **后果**：派单第 9 节要的那一格验收，正确答案是「`backend/data` 一个字节都没动」而不是「只多出 `golden_cases.json`」；照派单去核会以为漏改了一个文件。
2. **这份文件没有指纹常量，P9-A3 的六步里第 4/5 步不存在**。派单要「先算新指纹 → 改文件 → 用 `read_bytes()` 复核 CRLF → 改常量 → 跑指纹测试 → 另四个指纹逐字不变」。实测全仓 5 组指纹（国标 CSV / `exercises.yaml` / `exercise_equivalence.yaml` / `alert_rules.yaml` / 18 套模板）**一个都不在 `golden_cases.json` 上**，`Grep -n "golden_cases|GOLDEN"` 也没有任何指纹常量指着它。故第 4/5 步**无从执行**；我按剩下的四步照办，并补做了等价物（改前改后各给两个 sha256 + 变异自证 3/3）。
3. **`GET /api/alerts?rule_id=…` 这个筛选不存在**（简报第 ⑤ 步）。泛型 CRUD 的 list 端点只有 `limit` / `offset`（`app/api/crud.py::list_rows` 的签名是 `page: Page = Depends()`），FastAPI 会**静默忽略**未知查询参数。三条候选处置见第 ③ 节，采「打 `?limit=200` + 客户端过滤 + 断言恰好 1 条且 `total == 2`」——⚠️ 那其实是**更强**的断言。
4. **spec §9.1 的勘误内容按实际写，不按计划正文写**。计划要「大屏的两个阈值从『硬编码在散文里』改成『落在 `alert_rules.yaml` 的 `screen:` 段』」。实测 `alert_rules.yaml` 里**没有 `screen:` 段**，两个阈值住在 `app/domain/report.py` 的 `SCREEN_GAP_DAYS` / `SCREEN_RPE_MAX`（Task 8 的裁定 P8-A6，两条理由：那份 YAML 的所有者是「5 条**判据**的阈值」而这两个数不产生工单；加它要走 P9-A3 六步程序而收益只是「两个数换个文件住」）。⚠️ 照计划正文写会让 spec **说一件没发生的事**，而那正是本 Task 要清的那一类错误。故勘误写成「住址是 `app/domain/report.py`、**不是** YAML，理由是 P8-A6 那两条，代价是专家想两边一起调松要改两个文件走两套评审，而归 #11 不新开编号」。
5. **`test_layering.py` 那两条注释的「当前值」不是 90 / 36，而是 130 / 38**（勘误 #10）。控制者给的是「写着 69→90、18→36」。实测（与那条测试**同一个口径**：`BACKEND.rglob("*.py")` 与「按 `names` 展开的相对导入计数」）是 **130** 与 **38**。⚠️ 差额的成因我**没有完全定死**，两个候选：① `backend/scripts/demo_bootstrap.py` 是本 Task 新建的（+1），但那解释不了 39 的差；② 更可能的是控制者的 90 数的是 `git ls-files`（**入库**文件）或只数了 `backend/app/**`，而那条测试数的是 `backend/**/*.py`（**含 47 个测试文件**）。⚠️ 按硬规矩 #109（亲验跑出不符项时先用第二个独立工具复核）我用 AST 与 `rglob` 两个口径各数了一遍，两者一致；**故我在注释里写的是「Plan 03 Task 9 结案时的当前值是 130 / 38」并附上命令**，让下一个人能自己复算，而不是写一个我无法解释来由的数。
6. **`demo.ps1` 不用 `run_backfill`**（简报 Task 9「决定」第 3 条 vs 派单第 7 节「`demo.ps1` 里也不要有它们」）。两处冲突，**采派单**，理由与代价见第 ⑤ 节（一次 `run_daily` 就走完九个阶段、60 人约 3 秒；代价是演示库里「周环比流动」恒为 `has_previous = False`，已写进 bootstrap 的模块 docstring）。

### 没按派单做的地方（**1 处**）

* **TDD 的 RED 步骤在端到端这一条上是「变异代替」而不是「先写测试看它红」**。GC14 那一条我照做了（先改 `== 13` → `== 14`、亲眼看到 `AssertionError: assert 13 == 14`，再写夹具转绿）。而 `POST /api/pipeline/run-daily` 在本 Task 之前**根本不存在**，测试先写的话红的是「路由不存在」——那一格红的信息量与 **M1 变异**（删掉 `include_router(pipeline_router)` 那一行 → ① 得 404）完全重复。故我把端点与测试一起写，然后用 M1 当作它的 RED 证据。⚠️ 两者证明的是同一件事（这条测试真的能抓到「API 层没接上」），但**顺序确实与派单的「TDD 先红后绿」不同**，如实报。
* 其余 0 处：四个交付物、19 条勘误、5 个 commit 的划分、报告 9 节、探针放 `t9_probes/`、`git add` 按文件名逐个加、commit 信息 UTF-8 无 BOM + `-F`、不 push、不切分支、不碰 `main`、不跑那三个 CLI、`backend/data/**` 一个字节不动 —— 全部照办。

### 关切（**7 条**，都不在本 Task 的授权范围内改）

1. **`GREEN_MASTERY` 读的 `normalized_score` 与进步榜算的不是同一个数**（第 ④ 节）。移交 Plan 04。
2. **重放历史业务日时 `weekly_class_report.alert_summary` 恒为 9 个 0**（第 ⑤ 节 (e) 之后那一段）。根因是 `run_daily` 注入的 `now` 是真实时钟、而 `as_of` 可以是历史日期，两者不同源。生产上 `as_of == 今天` 故不可达；演示与重放可达。修法是让 `run_daily` 的 `now` 也可注入，那是一次签名变更、会连带 Task 7/8 两条「同一个 `now`」的断言。
3. **`POST /api/pipeline/run-daily` 在 `status == "failed"` 时仍回 200**。理由：`app.api.errors` 的模块 docstring 逐字写着 `_INTERNAL_MESSAGE` 是**唯一**允许出现在 500 响应体里的字符串（防泄漏），而本档要回的恰恰是 `error_summary` 那一句具体的话。与 `POST /api/mini-tests/batch` 那条已登记的关切同形。⚠️ 测试一律断言 `status == "success"`，故这一档在测试里是响的。
4. **`POST /api/class-sessions` 今天完全匿名可写**（`class-sessions` 在 `RESOURCES` 里是 `writable=True` 且**没有** `scope`，泛型工厂因此不挂任何 `Security`）。⚠️ 它是本 Task 端到端测试第 ③ 步用到的端点，故我**亲验**了这件事（不带任何请求头 → 201）。任何调用方都能给任何教学班排一节课、并设 `rpe_opened=True` + 自己挑的 `rpe_token`，于是「学生猜 `class_session_id` 乱交」那道口令闸门被绕过。→ Plan 04 收窄写入端点时应一并处置（派单 #19 的第 2 条只点了三个写入端点，**漏了泛型工厂这一整圈**）。
5. **教师端的预警队列没有筛选**（`rule_id` / `status` / `level`）。一个 500 人的学期跑到第 16 周，`alert` 表会有几千行，而 list 端点只有分页。→ Plan 04。
6. **`prescription_stage` 的 warning 日志措辞过宽**：它对 `safety.warnings` 的**每一条**都打「学生 X 的处方（模板 Y）**需要人工复核**：…」，而 `prescription.status = "needs_review"` 只由「安全规则命中却找不到等价动作」置位。演示库实测：日志打了 18 条「需要人工复核」，而 `status == "needs_review"` 的处方是 **0** 张（那 18 条说的都是「addon 的训练量未指定」，那是「教师需要用 `VOLUME_SCALE` 定一个量」，不是「这张处方不能执行」）。⚠️ 这是一句**让人误判严重性**的日志。→ 改它是改生产行为（可能有 `caplog` 断言），不在本 Task 范围；已在 `demo_bootstrap.py` 的输出里当场把两者的差别说清。
7. **`_stratification_payload` 与 `input_snapshot_of` 一正一逆、两个所有者**（#19 第 4 条）。已写明，未合并。

### 待清扫（**5 条**，都是「纯散文精度」，按 Ruling 5 不在本 Task 做）

1. `app/api/routers/catalog.py` 的模块 docstring 里那张 23 行对照表与 `RESOURCES` 的**书写序**是两份需要人工同步的清单（今天一致，但没有守卫）。
2. `app/api/schemas/dashboard.py` 的「**16** 个模型」与 `tests/api/test_dashboard.py::…== 16` 是两份，改一处不改另一处会红——这是**好的**，但那个 16 的**来源**（哪 16 个）只在测试的字面清单里，schema 模块自己没列。
3. `app/pipeline/daily.py` 的模块 docstring 说「spec §5 的十阶段里，Plan 01 落地前五个 + 第十个……Plan 03 Task 8 插入第八个」，而 §5 的第 7 阶段（`Aggregate`）与第 9 阶段（`Weekly`）的编号在正文里与「第 8 个阶段」的说法**混着用**（`report_stage.py` 的第一行说它是「**第八个**阶段」，同一句话又说它「= spec §5 的第 **9** 阶段 `Weekly`」）。两个数都对、主语不同（一个是本仓的阶段序、一个是 spec 的编号），但没有一处把两套编号并排列出来。
4. `tests/api/test_crud.py` 里 `running_total == 19` 那一格是**跨资源**的合计，而它的 19 个组成部分散在 23 行 `RESOURCES` 的声明里，加一个资源时要回来改它——`docstring` 已经警告过（「它把『某一张表的探测结果是空集』也算进去」），但没有守卫说明「19 是怎么来的」。
5. `Document/…设计spec.md` 的 §13「运行方式」那一段仍是 Plan 01 的四条命令（`python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily` / `uvicorn`），而本 Task 之后**第一条与第二条会写禁区**、第四条少了 `PE_DB_URL` 那一步、且没有提 `demo.ps1`。⚠️ 这一条其实接近 Critical（照它跑会破禁区），但它改的是 spec 的**运行手册**而不是勘误，且本 Task 的授权是「§14 补项 + 各节勘误」，故留待清扫并在此显式报出。

---
""")

BLOCKS.append("""## ⑧ 最终验收

探针：`t9_probes/p13_final_acceptance.py`（全部运行时口径；端点数走 `app.openapi()["paths"]`，定义份数走 AST，行尾/字节走 `read_bytes()`）。

| 验收格 | 基线（`cf9ad7a`） | 结案（`9c0b1e9`） | 判据 |
|---|---|---|---|
| `python -m pytest -q` | 1225 passed | **1244 passed** | +19 = GC14 参数化 1 + 端到端 5 + 支 I 12 + report_stage 新档 1 |
| 覆盖率四格（`--cov=app.domain --cov-branch`） | 1259 / **0** / 376 / **0** / 100% | **1268 / 0 / 376 / 0 / 100%** | ⚠️ stmts +9（全在 `report.py`：112 → 121），**Miss 与 BrPart 仍是 0**（spec §12 的硬要求）；带 `--cov` 时是 1243 passed + 1 skipped |
| 表数 | 25 | **25** | `len(Base.metadata.tables)` |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33**（不动） | AST 数 `test_models.py` 里那个 list 的元素个数 |
| 架构守卫扫描面 | 58 | **60** | pipeline 10 + db 11 + domain 18 + api **19 → 21**（新增 `routers/pipeline.py` 与 `schemas/pipeline.py`） |
| `/api/` 路径模板 | 62 | **63** | `app.openapi()["paths"]`（+ `POST /api/pipeline/run-daily`） |
| 操作数 | 90 | **91** | 同上 |
| 挂 `security` 的操作 | 17 | **18** | 同上；`test_prescription_api.py` 那份「除清单之外无 security」的 18 项清单同步登记 |
| 黄金用例 | 13 | **14** | `len(json["input"])`；学号 `GC01…GC14` 连续无空洞 |

### 五个指纹（现算自磁盘，与测试里的字面量各一份 —— 两侧不同源）

| 文件 | 期望（测试里的字面量） | 现算 | |
|---|---|---|---|
| `backend/data/national_standard_2014.csv` | `D2C8E539E2FA0029` | `D2C8E539E2FA0029` | ✅ 逐字不变 |
| `backend/data/exercises.yaml` | `5394B37F01DAC9AC` | `5394B37F01DAC9AC` | ✅ 逐字不变 |
| `backend/data/exercise_equivalence.yaml` | `822CB86A5E998301` | `822CB86A5E998301` | ✅ 逐字不变 |
| `backend/data/alert_rules.yaml` | `E48E3AC82BB45BB7` | `E48E3AC82BB45BB7` | ✅ 逐字不变 |
| `backend/data/prescription/*.yaml`（18 份） | `TEMPLATE_FINGERPRINTS` 18 条 | 18 份逐个对账 | ✅ **18/18 逐字一致、0 份不符** |

⚠️ 第一次对账时我用了**文件名**当键（`GRN-END-ABN-13.yaml`），得到 18 个 `None`；换成 `p.stem`（`GRN-END-ABN-13`）后 18/18 一致。**这是探针的错、不是仓库的错**，如实记下（硬规矩 #109：跑出不符项先用第二个独立口径复核，才允许当成发现）。此外那四条指纹测试与 `test_template_yaml_fingerprints_are_pinned` 在全量里都绿，是第三个独立口径。

### `golden_cases.json` 的新指纹（这份文件**没有**指纹常量，两个数供后续对账）

`43 571 B / 892 行` → **`51 619 B / 959 行`**；CRLF **959** / bare LF **0**。
sha256[:16]：as-is `A08B6AE9A463BBA3` → **`39FC9C29D9106C47`**；CRLF→LF `E0E2DABA0FE97344` → **`9FB1C619F896D418`**。
`git ls-files --eol` 仍是 `i/lf w/crlf attr/`（与改前同一种）。

### spec 的字节与行

`128 328 B / 1 093 行` → **`163 922 B / 1 230 行`**；CRLF **1 229** / bare LF **0**（改前 1 092 / 0）；sha256[:16] `7C92ED5C049CC15E` → `32329DD43DF6981C`。
§14 表格 **40 行**、首行 `| 1 |`、末行 `| **40** |`（用「数换行 + 校验首尾两行」，**不用正则抽编号**——#155 的成因正是那个正则只匹配到未加粗的 1–17）。

### 禁区与 `git diff`

| 判据 | 结果 |
|---|---|
| `backend/pe.db` 存在 | **False** ✅（`demo.ps1` 真跑一次之后、以及全量测试之后各复核一次） |
| `backend/data/seed/` 的文件数 | **0** ✅ |
| `git diff --stat cf9ad7a HEAD -- backend/data` | **空**（一个字节都没动）✅ ⚠️ 派单预期「只多出 `golden_cases.json`」，而那份文件在 `backend/tests/fixtures/` 下，见第 ⑦ 节顶回 1 |
| `git diff --stat cf9ad7a HEAD -- backend/tests/fixtures` | `golden_cases.json | 99 ++++----`，1 file changed, 83 insertions(+), 16 deletions(-) ✅ **只有它** |
| `backend/pe_demo.db` | 存在（`.gitignore:38` 实测在忽略清单内，`git status` 干净）✅ |
| `git status --porcelain` | 只有 `.superpowers/sdd/…/t9_probes/` 与 `task-9-brief.md` 两个未入库项 ✅ |
| `cf9ad7a..HEAD` 改动的文件 | **36 个**：`Document/…spec.md` 1 + `backend/app/**` 16 + `backend/scripts/**` 2 + `backend/tests/**` 17。⚠️ **`backend/data/**` 0 个** |

### 行尾纪律（硬规矩 #89 扩写：数行尾用 `read_bytes()`）

改过的 14 个代码/测试文件逐个用 `git ls-files --eol` 复核：**`i/` 一律 `lf`，`w/` 的行尾种类与改前逐个一致**（`app/api/routers/feedback.py`、`app/pipeline/alert_stage.py`、`app/pipeline/report_stage.py`、`app/domain/report.py` 是 `w/lf`，其余是 `w/crlf`）。⚠️ 中途出过一次事故并已修：`w07` 的替换助手对**单行锚点**优先选中 LF 版候选，于是往两个本来全 CRLF 的文件里插进了 4 + 4 个裸 LF；`w08` 用 `read_bytes()` 复核后一律折回 CRLF，并断言「行数不变」（798 + 4 = 802、1157 + 4 = 1161）。**没有用 `git checkout` 还原任何文件**（硬规矩 #46）。

### 变异取证汇总（**10 条，10/10 killed**）

| 组 | 变异 | 结果 |
|---|---|---|
| GC14 | M1 `safety_substitution_count` 32 → 0 | KILLED |
| GC14 | M2 `week1_block0_exercise_ref` 替身 → 原 ref | KILLED |
| GC14 | M3 `curr.weight_kg` 95.0 → 78.0（bmi 31.0 → 25.5） | KILLED |
| 端到端 | M1 删掉 `include_router(pipeline_router)` | KILLED（api → pipeline 接缝） |
| 端到端 | M2 `AUTO_REDUCTION_FACTOR` 0.8 → 0.85 | KILLED（pipeline → api 读侧接缝） |
| 端到端 | M3 推送标题「减 20%」→「减 25%」 | KILLED（api → notify → 学生端接缝） |
| 进步榜 | M4 `0.5 * tied` → `0.0 * tied` | KILLED（8 条红） |
| 进步榜 | M5 composite 先 round 百分位再平均（56.67 → 56.66） | KILLED（3 条红） |
| 进步榜 | M6 `_composite_of` 改回读 `normalized_score` 列 | KILLED（3 条红）← 本次裁定要修的那个缺陷 |
| 进步榜 | M7 往 `report_stage.py` 塞第二份 `shuttle_percentile` | KILLED（AST 守卫报 `3 != 2`） |

⚠️ **10 条都是一次就 killed，没有一条存活**，故本 Task **没有** Task 8 那个「先写测试 → 变异存活 → 补反例 → killed」的形状可报。⚠️ 而 M6 与 M2（GC14 组）是**最接近存活**的两条：它们打的都是「一份数据换一个来源」这一类改动，而这类改动最容易让测试变成哑弹——M6 红说明 `_mini` 助手改成「给原始测量值」之后那两条进步榜测试**不再**依赖 `normalized_score` 列，M2 红说明 `week1_block0_exercise_ref` 那一格真的在钉「替换发生过」。

---

## ⑨ commit sha

| sha | 一句话 |
|---|---|
| **`db3eec0`** | ① GC14：`golden_cases.json` 加第 14 例（`bmi = 31.0` → `RED-SPD-ABN-05` → 32 次等价替换、blocks[0] 是替身 `stationary_cycling`），让 spec §7.4「BMI > 30」那一档在黄金用例里第一次真的命中；连带 3 条相等断言（`== 13` → `== 14`）与 7 个文件里 28 处「13 例 / 13 人」的散文（只改当前事实、不动历史陈述） |
| **`491c4e7`** | ② `POST /api/pipeline/run-daily`（+ `app/api/routers/pipeline.py` 与 `app/api/schemas/pipeline.py`）与端到端冒烟 `tests/api/test_end_to_end.py`（5 条，主测试一条走完八步、真实 HTTP） |
| **`de95ef6`** | ③ 周报的进步榜在**生成时**算标准化得分；算式（`shuttle_percentile` / `mini_test_scores` / `SCORE_PRECISION`）从 `app/api/routers/feedback.py` 提到 `app/domain/report.py` 一个住址，AST 守卫数定义份数 == 2 |
| **`ec6a65f`** | ④ `backend/scripts/demo.ps1`（UTF-8 带 BOM）+ `demo_bootstrap.py`：一条命令删旧库 → 灌数据 → 起 uvicorn → 打印八个可点的 URL；`-DryRun` 跑完不留文件 |
| **`9c0b1e9`** | ⑤ spec 勘误（§14 补 #38/#39/#40 + 10 处章节勘误）与 19 条待清扫逐条落地（代码/测试侧 29 处、14 个文件） |

⚠️ **未 push、未切分支、未碰 `main`**。工作树在 `9c0b1e9` 上干净（只有 `.superpowers/` 下两个未入库项：本报告所在的 `t9_probes/` 与派单 `task-9-brief.md`）。

### 取证探针清单（全部在 `.superpowers/sdd/2026-10-08-实施计划03-反馈预警与CRUD-API层/t9_probes/`，**不在 `backend/` 下**，硬规矩 #108）

`p01_baseline.py`（基线量）· `p02_gc14_design.py`（18 套模板的 high block 与 addon 冲击等级）· `p03_gc14_notes.py`（既有 13 例的 note / 得分）· `p04_gc14_build.py`（构造 GC14、跑完整链路、并验证既有 13 例零影响）· `p05_gc14_handcheck.py`（38.4 与 [116,137] 的手算复核）· `p06_json_roundtrip.py`（`json.dumps` 能否逐字往返）· `p07_meta_facts.py`（hr_zone 与 sample_size 的事实）· `p08_gc14_mutations.py`（3 条变异）· `p09_e2e_dryrun.py`（端到端场景的进程内预演）· `p10_e2e_mutations.py`（3 条变异）· `p11_progress_board_mutations.py`（4 条变异）· `p12_live_server_evidence.py`（对真 uvicorn 打一遍闭环）· `p13_final_acceptance.py`（最终验收的全部运行时口径）
落地脚本：`w01_write_gc14.py` · `w02_thirteen_fallout.py` · `w03_commit.py` · `w04_append_report_tests.py` · `w05_write_demo_ps1.py` · `w06_spec_errata.py` · `w07_code_errata.py` · `w08_fix_bare_lf.py` · `commit.py`（通用提交器）· `w09_report_part1.py` · `w10_report_part2.py`
""")


def main() -> int:
    text = "".join(BLOCKS)
    raw = text.replace("\n", "\r\n").encode("utf-8")
    with TARGET.open("ab") as handle:
        handle.write(raw)
    after = TARGET.read_bytes()
    crlf = after.count(b"\r\n")
    bare = after.count(b"\n") - crlf
    lines = crlf + bare + (0 if after.endswith(b"\r\n") else 1)
    print(f"追加后 {TARGET}")
    print(f"  bytes={len(after)} lines={lines} CRLF={crlf} bare LF={bare}")
    print(f"  sha256[:16]={hashlib.sha256(after).hexdigest()[:16].upper()}")
    assert bare == 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
