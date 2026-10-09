# SDD ledger — plan: Document/2026-10-08-实施计划03-反馈预警与CRUD-API层.md

# 实施计划 03：智慧反馈层 + 预警 + 全系统 CRUD API —— 执行账本

**计划**：`Document/2026-10-08-实施计划03-反馈预警与CRUD-API层.md`（75 321 B / 435 行 / 纯 LF）
**分支**：`feature/plan-03-feedback-alert-crud-api`（从 `main` = `a5f16b1` 开出）
**执行方式**：Subagent 驱动（`superpowers:subagent-driven-development`）—— 用户在 Plan 01 时已选定，Plan 02 沿用，本计划继续
**上游**：Plan 01（Rulings 1–234、硬规矩 #1–#47）与 Plan 02（Rulings 1–158、硬规矩 #48–#94、控制者错误 158 条）的账本在同级的两个目录里。**本计划受那 94 条硬规矩全部约束。**

**代码基线（Plan 02 结案 = `main`）**：`807 passed`、`app/domain/` **996 stmts / Miss 0 / 288 branch / BrPart 0 / 100%**、**18 张表**、`app.domain.prescription.__all__` **51**、`_MODELS_PUBLIC_BASELINE` **33**、架构守卫扫描面 **35**（pipeline 8 + db 11 + domain 16）、SQLAlchemy **2.1.3**、Python 3.11.1（无 venv）。

**本计划新增的依赖**：**零**。fastapi 0.141.1 / uvicorn 0.54.0 / httpx 0.28.1 / pydantic 2.13.5 / starlette 1.7.0 **全部已装**，且 `backend/pyproject.toml` 早已声明（控制者亲跑 import 冒烟坐实）。

---

## Rulings（预检裁决，执行前生效）

### Ruling 1 —— 用户裁定「只要能运行起来的原型系统就好」，本计划的严格度据此再降一档

**用户原文（2026-10-08，两次）**：
> 「项目只要能运行起来的原型系统就好。」
> 「后端其实只要不出太大的 bug 就行，后端算法层面要求不是很高，主要是要做一个系统，类似管理型的原型系统，需要能够进行增删改查，然后加上之前的大数据算法即可，在进行前端页面后尽量保持简洁，功能齐全，与后端能够对齐。」

**裁定 —— 相对 Plan 02 的 Ruling 145 再放宽三处**：
1. **每个 Task 的预检扫描保留，但只做一份探针脚本**（Plan 02 后期是 3–4 份）。**保留的理由是实测的**：Plan 02 的 9 个 Task，预检**每一轮都查出 2–4 条 Critical**，且**全部是同一族**——「计划引用了一个不存在的东西」（Task 5 的 `weekly_volume` 基准量、Task 6 的 `microcycle_weeks` 列、Task 7 的 `PersonInputs.height_cm`、Task 9 的「夹具缺身高体重」）。**这一族的失效形态是「实现者照做会当场炸、或做出来是假绿」，砍掉预检的代价远高于它的成本。**
2. **变异测试只在 Task 6（预警阈值）要求**，其余 8 个 Task 不做。**理由**：预警阈值是本系统里唯一会直接改变「给哪个学生推减量 20%」的量，而这类错误在端到端测试里看不出来（少触发一条预警，500 人的分布测试只动几个百分点）；而 CRUD 层的错误会被 HTTP 状态码断言当场抓到。
3. **每个 Task 目标 0–1 轮 fix round**（Plan 02 后五个 Task 的实际值是 1/0/1/0/0）。

**没有放宽的（一条都不许砍）**：TDD；`app/domain/` 分支覆盖 **100%**（含新增的 `alerts.py`）；单一所有者；断言两侧不同源；架构守卫全绿（**且本计划要给守卫加 `api` 这一层**）；Plan 01/02 的全部既有测试仍全绿；三个指纹；每个 Task 一轮评审。

### Ruling 2 —— 本计划刻意不做的四件事（全部有出处，不是遗漏）

| 不做的 | 出处 | 理由 |
|---|---|---|
| `HttpLePaoAdapter` 的真实实现 | 计划的「刻意不做」第 1 条 | 骨架已在（`app/adapters/http_lepao.py`，78 行，四个方法一律 `raise NotImplementedError`）。**它自己的 docstring 逐字写着**「本文件刻意**不含**任何 HTTP 客户端、重试、鉴权与超时逻辑：接口字段未定时写这些只是猜测，而猜测出来的重试策略会在真实接口确定后变成需要拆掉的负担」，以及「真实实现落地时**必须补齐对应的行为契约测试**，不得沿用『两个实现跑同一组契约测试』这种说法」。原型用 `MockLePaoAdapter` 就能跑通全链路，而真实实现要补约 40 条行为契约测试且**接口字段今天未定** |
| 真实消息推送 | spec §8.3 原文 | 「原型不做真实推送（需微信订阅消息资质 / 短信通道）」。只做 `InAppChannel`，另两个通道建骨架 + 契约测试（与 `http_lepao.py` 同构） |
| 真实鉴权 | 计划的 Task 1 决定 | 用请求头传身份（`X-Student-Id` / `X-Teacher-Staff-No`），并在 `deps.py` 的 docstring 里明写「原型口径，上线前必须换成真实会话」。**⚠️ 但 Review Focus 第 1 条的「作用域闸门」照做**——没有鉴权不等于没有授权检查，否则前端一上线就是任意读写全库 |
| 性能压测 | 用户 2026-10-08 裁定 | Plan 02 已删掉 Task 12 的 p95 压测，本计划不恢复。spec §1.3 的两条量化验收在 spec 里已写明「未测量」 |

### Ruling 3 —— 计划自审（writing-plans 的 Self-Review）查出 6 处，已全部就地更正

控制者按 `writing-plans` 技能的五项自审清单核了一遍刚写完的计划，**查出 6 处自相矛盾或事实错误**，用 `_selfreview.py` 更正（**9 处替换全部命中 1 次**，逐条 `assert` 命中数，硬规矩 #79；改完还跑了一次「6 处矛盾是否真的消失」的反向复核，全部 0 命中）：

| # | 自审项 | 查出的问题 | 更正 |
|---|---|---|---|
| 1 | 第 3 项（类型一致性） | `build_crud_router` 的签名里写了 `deletable: bool = True`，而同一个 Task 的决定段又写 `deletable="forbid"` —— **`bool` 不能等于字符串** | 去掉 `deletable`，`on_delete` 的三个取值 `"restrict"` / `"cascade"` / `"forbid"` 已覆盖它（`"forbid"` → 405）；同时把 `list_exclude` 补进签名（决定段用了它、签名里没有） |
| 2 | 第 3 项 | Task 3 说 `exercise` / `prescription_template` 是 `writable=True`，而「计划完成后的状态」那段说 `writable=False` 并写着「这条推翻了 Task 3 里的说法」—— **同一份计划里两个相反的结论** | **以只读为准**（spec §4.4 逐字：「这是体育专家维护的知识资产而非业务数据，改阈值应走版本控制与评审，不应在运行时改数据库」；开放 API 写它们会让「YAML 是唯一所有者」变成假的，因为下一次 sync 会静默覆盖）。Task 3 的正文已改定，尾部那句「推翻」改成「已写定」。**⚠️ 这顺手解决了 Plan 02 传导过来的第 8 条**（`sync_*` 没有生产调用方）：由 `POST /api/pipeline/run-daily` 调一次，两个都幂等 |
| 3 | 第 3 项 | `Alert` 的唯一约束用了 `semester_id` 与 `window_key` 两列，而**字段清单里没有它们** —— 后面用了、前面没定义 | 两列补进字段清单（`semester_id: int` FK、`window_key: String(32)`），并在字段清单里就写明「这一列 spec §4.6 没有 → 登记 §14 #38」 |
| 4 | 第 2 项（步骤扫描） | Task 8 的决定段写「`notification.alert_id` 要加 `ondelete="SET NULL"`，**这一条要回改 Task 2**」—— 这正是 Plan 02 控制者错误 #151 的形状（**说要改而没落笔**，然后派一件「复核」的活） | **直接在 Task 2 的字段清单里写定**，Task 8 那句「回改」删掉、改成「已写进 Task 2 的字段清单，不留『回改』」 |
| 5 | 第 5 项（比例/数字） | 「`_BATCH_OWNED_TABLES` 要从 5 张扩到 **10 张**」—— 实算是 **9 张**（既有 5 + 新增 4；`rpe_record` / `mini_test` / `notification` 三张刻意不带 `batch_id`） | 改成 9，并把「既有 5 张是哪 5 张、新增 4 张是哪 4 张、哪 3 张刻意不带」逐个列名，末尾加「**自己用运行时口径数一遍再写进断言，不要照抄本行**」（硬规矩 #89） |
| 6 | 第 5 项 | 「7 张新表里有 **9 个 `JsonText` 列**」—— 实算是 **7 个**（`mini_test.item_combo` + `alert.trigger_snapshot` + `weekly_class_report` 的 5 个），故 `len(json_text_columns)` 从 14 → **21** | 改成 7 与 21，逐个列名，同样加「自己数一遍」 |

**⚠️ 元观察（值得记下来）**：这 6 处里有 **3 处（#1/#3/#5）是「同一个量在计划的两处写了不同的值」**，**2 处（#2/#4）是「说要改而没落笔」**。前者是 Plan 02 控制者错误 #141 的形状（派单里两个口径互相打），后者是 #151 的形状。**即：这两族错误在「写计划」这个动作里的发生率，与在「派单」里一样高。** 而 writing-plans 技能的第 3 项（类型一致性）与第 2 项（步骤扫描）**恰好就是针对这两族的**——**自审清单不是仪式，它这一轮真的抓到了 6 条。**

**→ 补硬规矩 #95：写完计划/派单，必须逐条跑一遍 `writing-plans` 的五项自审，并把「查出几处、分别是什么」记进账本；查出 0 处也要记（0 处是一个需要解释的结果，不是一個需要庆祝的结果）。** 依据：Ruling 3 —— 6 处里有 5 处是控制者在 Plan 02 已经犯过的同型错误，说明「在另一个文档里重犯」的概率与「在同一个文档里重犯」相当。

---

## 任务进度

（尚未开始。Task 1 是 FastAPI 骨架 + 依赖注入 + 作用域闸门。）

---

## 开工前的计划冲突扫描（SDD 技能的 Setup 步骤；控制者亲跑于 `5b4a10c`）

**方法**：技能要求「一张表，不是一个结论」——**每一对共享文件或接口的任务一行**（一方产出什么 vs 另一方消费什么、查出什么），**每个任务一行**（它自己的正文是否自洽：它指定的测试 vs 它指定的代码、它创建的文件 vs 它后面又改的文件）。

### A. 任务对之间的冲突（共享文件 / 共享接口）

| # | 任务对 | 共享的东西 | 查出什么 | 裁定 |
|---|---|---|---|---|
| **S1** | **T7 ↔ T8** | `app/api/routers/alerts.py` | **顺序反了**：T7 的 Files 写「**Modify** `alerts.py`（**Task 8 建**，这里只加『处理预警』端点）」，而 T8 的 Files 写「**Create** `api/routers/{dashboard,alerts}.py`。**T7 跑在 T8 之前**，它要改一个还不存在的文件 | **T7 创建 `alerts.py`**（含 `POST /api/alerts/{id}/handle`），**T8 只创建 `dashboard.py`**、并把 `alerts.py` 从它的 Create 清单里挪到 Modify（若它需要加端点）。**这是 Plan 02 控制者错误 #151 的同型**（说要改一个不存在的东西）——**已更正两处正文** |
| **S2** | **T2 ↔ T7** | `weekly_adjustment` 表 + `tests/db/test_models.py` | T7 要给 `weekly_adjustment` 加 `UniqueConstraint("prescription_id", "week", "reason", "source")`（防「同一周重复触发把系数连乘成 `0.8³ = 0.512`」），而**那张表是 Plan 02 Task 6 建的、`test_models.py` 的断言由 T2 统一改**。两个 Task 都要动同一张表的 schema 与同一份测试 | **把这条唯一约束挪进 T2**（它是 schema 变更，而 T2 是本计划唯一的建表 Task）。**理由**：schema 变更分散在两个 Task 会让「表数 18 → 25」与「约束清单」两个断言的改动点跨 Task，而 Plan 02 的 P6-A5 已经证明「一个数散落在多处」是最容易漏改的形状。**已更正两处正文** |
| **S3** | **T1 ↔ T2** | `tests/test_main.py` | T1 的 `test_health_reports_the_table_count` 断言 `tables == 18`（**字面写死**），而 T2 建成 7 张表后是 **25** → **T1 的测试会在 T2 当场变红**。计划正文只写了一句「Task 2 之后会变 25，那时同步改」，**但 T2 的 Files 清单里没有 `tests/test_main.py`** | **`tests/test_main.py` 加进 T2 的 Files（Modify）**。⚠️ 这正是硬规矩 #88 要防的形状（「列同步清单时，除了搜那个数本身，还要跑一次全量测试、把红掉的相等断言逐个收进来」）——**已更正 T2 的 Files 行** |
| **S4** | **T3 ↔ T5** | `POST /api/rpe-records`、`POST /api/training-logs`、`mini-tests` 的写入 | **同一张表两个写入口**：T3 的泛型 CRUD 会给 `rpe-records` / `training-logs` / `mini-tests` 各生成一个 `POST`，而 T5 又手写了 `POST /api/rpe-records`（带口令校验 + 服务端填 `submitted_at`）与 `POST /api/training-logs`（服务端算 `late`）与 `POST /api/mini-tests/batch`。**两条路由会撞**（FastAPI 按注册序取先匹配的，于是哪一个生效取决于 `include_router` 的顺序——一个没人看得见的耦合） | **`RESOURCES` 里这三个资源一律 `writable=False`（只读）**，写入**只走 T5 的特例端点**。理由：那三个特例端点各有一条**服务端才能算**的字段（`submitted_at` / `late` / 标准化得分），走泛型 CRUD 会让客户端能随便填——**而 `late` 是「完成率是 RCT 关键过程指标，必须严格」（spec §8.1 原文）的那一半**。**同理 `alerts` 也是 `writable=False`**（写入走 T7 的 handle 端点与 `alert_stage`）。**已更正 T3 的正文并给出 23 个资源的完整读写矩阵** |
| **S5** | **T6 ↔ T8** | `data/alert_rules.yaml` + 它的指纹常量 | T8 要往 `alert_rules.yaml` 加一个 `screen:` 段（大屏的两个阈值 + 班级周报「算法建议」的三个字符串与两个阈值），而 **T6 给这个文件加了一条 sha256 指纹测试**（照 `exercises.yaml` 的口径）→ **T8 改文件就必须同步那个常量**，而 T8 的正文一个字没提 | **T8 的 Files 加 `backend/data/alert_rules.yaml` 与 `backend/tests/test_refdata_alerts.py`（指纹常量）**，并按 Plan 02 Task 9 的 P9-A3 六步程序做（先算新指纹 → 改文件 → **用 `read_bytes()` 复核 CRLF 仍为 0** → 改常量 → 跑指纹测试 → 另两个指纹必须逐字不变）。**已更正 T8 的正文** |
| **S6** | **T1 ↔ T6** | `tests/architecture/test_layering.py` / `test_domain_purity.py` | T1 给守卫**加 `api` 这一层**（扫描面 35 → 43 左右），T6 给 domain **加一个模块**（`alerts.py`）。两个 Task 都改这两份守卫，且**都会动同一批下界断言**（`>=5` / `>=8` / `>=16` / `len(real_py) >=40`） | **不算冲突，但要写明口径**：T1 加层时把下界一次性抬到位（含 `api`），T6 只加一个 domain 模块、**不再动下界**（domain 16 → 17 仍满足 T1 抬过的下界）。**T6 的正文已加一句提醒**，免得它以为「扫描面涨了要说明」是要改断言 |
| **S7** | **T3 ↔ T4** | `app/api/schemas/prescription.py` | T3 的 Files 写 **Create** 它，T4 的 Files 写「Create …（**补特例模型**）」—— **T4 是 Modify 不是 Create** | **T4 的 Files 改成 Modify**。措辞问题，不影响行为，但「Create 一个已存在的文件」会让实现者犹豫要不要覆盖 |
| **S8** | **T7 ↔ T8** | `app/pipeline/daily.py` | T7 改它（阶段序列插 `Alert` + 写 `alert_count` + `_replay_cleanup` 加 `Alert`），T8 也改它（插 `Report` 阶段 + 周日判据 + `_replay_cleanup` 加 `WeeklyClassReport`）。**顺序 T7 → T8，不冲突**，但 T8 的实现者要看到 T7 改后的形状 | **不算冲突**（严格串行）。**T8 的正文已加一句**：`_replay_cleanup` 的清单在 T7 之后是 7 张（含 `Alert`），T8 加 `WeeklyClassReport` 后是 8 张，**且子表先删的纪律仍适用**（`notification.alert_id` 带 `ondelete="SET NULL"`，故 `notification` 不进清单、也不会因删 `alert` 而炸 FK） |

### B. 每个任务的自洽性（它指定的测试 vs 它指定的代码）

| 任务 | 自洽吗 | 查出什么 |
|---|---|---|
| T1 | ⚠️ 一处 | `test_health_reports_the_table_count` 断言 `tables == 18`，**而 T1 自己不建表**——它断言的是 Plan 02 的终态。这条今天为真，但它是**一个会在下一个 Task 变红的字面断言**，而 T1 的正文没说自己造了这个债 → 见 **S3** |
| T2 | ⚠️ 两处 | ① Files 缺 `tests/test_main.py`（S3）；② `weekly_adjustment` 的唯一约束被推给 T7（S2）。**其余自洽**：7 张表的字段清单与 spec §4.5/§4.6/§4.7 逐格对得上，`batch_id` 的「4 张带 / 3 张不带」与 `_BATCH_OWNED_TABLES` 的 5 → 9 一致 |
| T3 | ⚠️ 两处 | ① `RESOURCES` 的 23 个资源**没有逐个声明 `writable` / `on_delete`**（正文只给了三档 `on_delete` 的语义与「只读资源是哪四个」，而 S4 又要把三个反馈资源与 `alerts` 也变成只读）→ **已补一张 23 行的完整读写矩阵**；② `schemas/prescription.py` 与 T4 的归属（S7） |
| T4 | ✅ | 六条「必须传导的 Plan 02 结论」逐条都能在 Plan 02 的账本里找到出处（P8-A3 / P8-A1 / P5-A3 / `OverrideRecord.reason` / `old_value`–`new_value` 是 `str` / P6-A2）。**`previous_had_overrides` 那一列实测存在**（Plan 02 Task 7 fr1 加的） |
| T5 | ✅ | 打卡 `late` 的三个模糊点各有一条决定与一条边界测试；完成率的分子分母口径明确（分母 = `Template.weekly_frequency`，**无处方返回 `null` 不是 `0`**）；`elapsed_seconds` 可为 `null`；`rpe_token` 用 `secrets` 而不是 `random`（并说明了理由） |
| T6 | ✅ | 5 条规则的判据逐条引了 spec §8.2 的原文与那张「四项均待确认」的口径表；`window_key` 的五种取值逐个给了算式；`GREEN_MASTERY` 的 `improve_pct` **明确写了它由谁消费**（Task 7 算 `mini_test_improved` 时），不会被当成死配置 |
| T7 | ⚠️ 一处 | Files 说 Modify `alerts.py` 而它还不存在（S1） |
| T8 | ⚠️ 一处 | 要改 `alert_rules.yaml` 却没说要同步指纹常量（S5） |
| T9 | ✅ | GC14 的三条边界都写明了（不改既有 13 例 / `muscle_low_p10` 仍不可达且**刻意留下并写明** / 例数 13 → 14 会让所有硬编码 13 的地方过期，按硬规矩 #88 先跑全量再收清单）；端到端冒烟的 8 步逐条给了断言点 |

### C. 裁定汇总

**8 条任务对冲突里，4 条是真冲突（S1/S2/S3/S4）、2 条是措辞（S5 的 Files 缺项算半条真冲突、S7）、2 条只是需要写明口径（S6/S8）。全部 8 条已更正计划正文。**

**⚠️ 元观察**：这 8 条里 **S1 与 S3 是同一族**——「一个 Task 说要改另一个 Task 才创建的东西」，而 Plan 02 的控制者错误 #151（派单声称「控制者已经改了 4 处」而实测 0/4 在树上）与 P6-A1（Task 6 的 Step 6 要在 Task 7 才建的管道上跑集成测试）也是这一族。**这是第 3 次。**
**→ 补硬规矩 #96：写「Modify X」之前，先确认 X 在那一刻已经存在；若它由后面的 Task 创建，就把创建挪到前面那个 Task，或把修改挪到后面。判据是 `git ls-files` 或本计划前序 Task 的 Create 清单，不是记忆。** 依据：S1 / S3 / Plan 02 的 #151 与 P6-A1。

**⚠️ 另一族**：S2 与 S5 都是「**一个改动会让另一个 Task 钉住的字面值过期**」（表的唯一约束、YAML 的指纹）。Plan 02 的 P6-A5（表数散落在六处）与 P9-A3（改 `exercises.yaml` 要同步指纹常量）是同一族。
**→ 补硬规矩 #97：任何「新增/修改一个被字面断言钉住的东西」的 Task，它的 Files 清单必须包含那份断言所在的文件——即使那个 Task 一行代码都不改那份文件。** 依据：S2 / S3 / S5 / P6-A5 / P9-A3。

**扫描后计划的 Files 清单变化**：T2 +2 个文件（`tests/test_main.py`、`weekly_adjustment` 的约束）、T4 的 Create → Modify、T7 +1 个 Create（`api/routers/alerts.py`）、T8 -1 个 Create（`alerts.py` 改 Modify）+2 个 Modify（`alert_rules.yaml`、`test_refdata_alerts.py`）。

**下一步**：抽 `task-1-brief.md` → 派实现者。**⚠️ 本 harness 的 Task 工具没有 model 参数**，故技能「Model Selection」那一节要求的「显式指定模型」在这里做不到——记录在案，不假装做了。
