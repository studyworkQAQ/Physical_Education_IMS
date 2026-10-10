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

---

## ✅ Task 1: complete (commits 69b4218..2832a27, 1 fix round)

**交付**：`59eb771`（`create_app` + `deps` + `errors` + `conftest` + `test_main.py` + `test_scope.py`，7 files / 1123 insertions）、`2832a27`（守卫加 `api` 层 + `.gitignore` 加 `pe_demo.db` + Step 4 冒烟取证）。

**验收（控制者本机亲跑复核，探针 `t1_probes/_verify.py` 已入库）**：
- 全量 **807 → 824 passed**（+17 = `test_main.py` 10 + `test_scope.py` 5 + `test_layering.py` 2）；带 `--cov` **823 passed, 1 skipped**
- `app/domain/` 四格 **996 / Miss 0 / 288 / BrPart 0 / 100% 逐字未变**（本 Task 不加 domain 代码，`app/domain/` 一个字节没动）✓
- **扫描面 35 → 38**（pipeline 8 + db 11 + domain **16** + **api 3**）；`backend` 全树 `.py` = **90**
- `app/api/` 今天 **3 个文件**（`__init__.py` 0 B、`deps.py` 9 400 B、`errors.py` 8 157 B）—— File Structure 列的 18 个是**计划结束时的形状**，Task 3–8 才建满
- **反向依赖亲扫**：`app/{domain,db,pipeline,seed}` 下**没有任何文件**含 `app.api` ✓
- **`/api/health` 响应原文** `{"status":"ok","tables":18,"students":0}`；`/openapi.json` 200（`paths=['/api/health']`）、`/docs` 200、`/redoc` 200、CORS 预检 200（`allow-origin: *`、`allow-headers: X-Student-Id`）、`/api/nope` → 404 `{"error":{"code":"not_found","message":"Not Found","detail":null}}`
- **禁区**：`backend/pe.db` **不存在**（连 `-journal`/`-wal`/`-shm` 四个全 False）✓；`pe_demo.db` 建出 172 032 B 且被 `.gitignore:38` 挡住（`git check-ignore -v` 亲验）✓；三个指纹 `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` **逐字不变**、CRLF 均 0；`git diff 69b4218 HEAD -- backend/data` **为空**；`data/seed/` 0 文件
- **签名亲验**（`inspect.signature`，与报告逐字一致）：`create_app(*, db_url: str | None = None) -> FastAPI`、`get_db(request: Request) -> Iterator[Session]`、`current_student(x_student_id: int | None = Header(None)) -> int`、`current_teacher(x_teacher_staff_no: str | None = Header(None)) -> str`、`require_scope(session, student_id: int, requester_id: int) -> None`；`Page.limit: int = 50 [Ge(1), Le(200)]`、`Page.offset: int = 0 [Ge(0)]`
- **偏离 ① 亲验成立**：`tests/` 下 34 个 `.py`、`__init__.py` **0 个** → 不建 `tests/api/__init__.py` 是对的（派单自己给的就是条件分支）
- **作用域闸门三条测试**（Review Focus 第 1 条）：`test_missing_identity_header_is_401`、`test_a_student_cannot_read_another_students_row`、`test_require_scope_is_a_pure_gate`
- **实现者自证的「新守卫有牙」三条探针**：G1（`_is_api_allowed` 换成裸 `startswith` → 判定矩阵红 3 格）、**G2（`app/domain/` 落一行 `from app.api import deps` → 新方向守卫红 **且** purity 白名单守卫也红 —— 这是坑 #3 的直接答案：不是误判，是正确地抓到了）**、G3（`app/api/` 落一行 `from app.seed.generate import …` → 方向守卫与既有 seed 守卫都红），还原后 `tests/architecture` 8 passed

### Ruling 4 — 实现者顶回 3 处 + 补充 1 处，**全部采纳**（Plan 03 的第 1–4 次顶回；累计 Plan 02 的 25 次 → **29 次，29 次都对**）

**顶回 1（采纳）**：`get_db` **必须多一个 `request: Request` 参数**。理由成立：无参版本只能从**模块级全局**取引擎 → 同进程两个应用会共用后建的引擎，而 `conftest` 的 `app` 夹具是 **function 级**（每个测试一个新 app、新引擎）。**对调用方零代价**（端点里仍写 `Depends(get_db)`，FastAPI 自己注入 `Request`）。控制者亲验签名确实是 `get_db(request: Request)`。

**顶回 2（采纳 → 控制者错误 #1，Plan 03 编号）**：**计划的三条要求互相不可能同时成立。** ① `db_url` 缺省取 `DEFAULT_DB_URL`；② Step 4 用 `uvicorn app.main:app`（模块级 `app` 由 `create_app()` **无参**建出，**命令行上没有任何位置能塞 `db_url`**）；③ 必须显式传 `db_url`、不落缺省。而 **`DEFAULT_DB_URL` 实测逐字就是 `sqlite:///…/backend/pe.db`**（控制者亲验）→ 三条凑一起的唯一结果就是 **Step 4 一跑就破 `pe.db` 禁区**。
实现者的处置：**加 `PE_DB_URL` 环境变量覆盖口子**（`DB_URL_ENV_VAR = 'PE_DB_URL'`），`create_app` 的取值序是「显式 `db_url` > 环境变量 > `DEFAULT_DB_URL`」，Step 4 的命令变成 `$env:PE_DB_URL = python -c "from app.main import DEMO_DB_URL; print(DEMO_DB_URL)"` 再 `python -m uvicorn app.main:app --port 8000`（**计划原命令逐字未变**）。
**⚠️ 控制者的坑 #1 嗅到了这个冲突**（逐字写着「起 uvicorn 时**必须显式传 `db_url`**，不能让它落到 `DEFAULT_DB_URL`」）**却没给「怎么传」的机制** —— 这是 Plan 02 控制者错误 #151 的同型（**指出了问题而没给出路径，等于把矛盾交给实现者**）。**→ 补硬规矩 #98：派单里写「必须 X、不得 Y」时，若 X 与 Y 在既有机制下不能同时成立，必须同时给出「怎么做到 X 而不 Y」的机制；给不出就是计划有洞，不是实现者的问题。**

**顶回 3（采纳 → 控制者错误 #2）**：**S6 的「下界一次性抬到位」不能按字面读成「抬到计划结束时的值」。** 控制者的原文是「抬的时候要给足余量（例如 domain 会从 16 涨到 17、`app/api/` 本计划要建约 15 个 `.py`）」—— **而「给足余量」与「下界」方向相反**：真按 53/56 写，Task 1 当场就红、并一路红到 Task 8。
实现者的处置：**抬到「今天已成立的地板之和」= 18**（pipeline 5 + db 5 + domain 5 + api 3；**5 沿用 `test_domain_purity.py` 已定下的那个数、不另发明**，api 的 3 是本 Task 实测），而「后面 8 个 Task 不再动它」用**单调性论证**兑现（剩下 8 个 Task 只增文件、不删不合并）。**并顺带核准了控制者数的另一个错**：计划 File Structure 逐行数出来 `app/api/` 是 **18** 个 `.py` 而不是派单说的「约 15」，故建满时聚合值是 **56** 不是 53。
**⚠️ 它还刻意没动 `>= 40` 与 `>= 16` 两条**，理由三条都成立：它们数的是 `backend/` 全树（实测已长到 90 / 36，两条都仍成立）、与「加一层」无关；`api` 层全用绝对导入故 `relative_seen` 一格没涨；**更要紧的是它们在 `test_domain_purity.py` 里各有一份镜像，只改一边破坏硬规矩 #51**，而 purity 不在计划的 Modify 清单里。

**补充 1（采纳）**：`errors.py` 在计划枚举的 4 条映射（`ValueError`→422 / `IntegrityError`→409 / `NoResultFound`→404 / 其余→500）之外**多注册了 `HTTPException` 与 `RequestValidationError` 两个处理器**。理由成立：**否则「统一响应形状」不成立** —— 403 / 401 / 404 / 请求校验 422 会仍是 FastAPI 缺省的 `{"detail": …}`，而这四个恰恰是 CRUD API 最常见的错误。**计划那句「统一响应形状 `{"error": {"code","message","detail"}}`」与它自己列的 4 条映射自相矛盾**（4 条盖不住「统一」这个词）→ **控制者错误 #3**。

### 实现者自查出的一处假绿（fix round 1，控制者认为这是本 Task 最有价值的一件事）

**Windows 上 `str(engine.url)` 把盘符的 `:` 编码成 `%3A`**，于是 `assert str(engine.url) != DEFAULT_DB_URL` **恒真** —— 它证明的不是「没落到缺省库」，只是「盘符被编码了」。**是红的那条把绿的这条一起暴露出来的**；三处一律改成 `make_url(...)` 结构化比对。
**⚠️ 这正是硬规矩 #92/#94 那一族的第 5 个成员**（#92：要求一条测试变红前先论证破坏在结构上可达；#94：说「某个分支可达」时要给出「它会被求值成真的那组输入在哪」）。**本次的形状是第三种：一条测试恒真，因为它比的是两个经过不同编码的字符串。**
**→ 补硬规矩 #99：断言「A 不等于 B」或「A 等于 B」时，若 A 与 B 任一侧经过了序列化/编码/格式化（`str(url)`、`repr()`、`json.dumps`、`os.fspath`），必须先证明这个变换是**单射**——否则断言可能在比较两个编码产物而不是两个值。URL、路径、日期是三个高发区。** 依据：本次的 `%3A`；Plan 02 的 #153（`read_text()` 把 `\r\n` 翻成 `\n`）是同一族在「读取」那一侧的发作。

### 6 处偏离派单字面：全部追认

① `tests/api/__init__.py` **没建**（控制者亲验 `tests/` 下 34 个 `.py`、`__init__.py` **0 个** → 按派单自己的条件分支不建）；② `conftest` 提供 `app`/`engine`/`client` **三个**夹具而非一个 `client`（`test_scope` 要在发请求前插两行学生，而 `StaticPool` 下那个 Session 必须关掉）；③ 计划说 6 条测试、实际 **15** 条（多出的 9 条各覆盖一个「计划写了但没人验」的性质；**点名的 6 条一条没少、名字未改**）；④ Step 3 的反向断言从「domain + db」扩到「`SCANNED_DIRS` 减 api」（**含 pipeline**，覆盖面更大）；⑤ 简报写基线 `5b4a10c`、派单写 `69b4218`，**两个 rev 都跑了**（控制者承认这是自己的不一致：简报是扫描前抽的）；⑥ 报告不在这 2 个 commit 里（照 Plan 02 惯例由控制者提 `docs:`）。

### 待清扫（推 Task 9）：**6 条**，Critical 级遗留 **0** 处

其中两条值得先记：① `test_layering.py` 里 `>= 40` / `>= 16` 的**注释实测值已陈旧**（写着 69→90、18→36，绑的是 Plan 02 Task 4 的时点但没标注）；② **`StaticPool` 没有 `checkedout()`**（本机实测 `AttributeError`；今天两条用到它的断言都跑在磁盘 URL 的 `QueuePool` 上，故撞不上 —— **但它是一颗等着被踩的雷**，Task 3 的 CRUD 测试全跑在内存库上时会撞上）。

### Ruling 5 — Plan 03 的评审席调整（控制者裁定，代价写明）

**裁定**：Plan 03 的「独立评审者」席位**折进控制者亲验**，不再每个 Task 派一个 reviewer subagent。计划 Ruling 1 原本把「每个 Task 一轮评审」列在**保留**项里，**本条是对它的收窄**。
**理由**：用户两次裁定「只要能运行起来的原型系统就好」，而 Plan 02 的实测成本是**每个 Task 一轮评审 = 一次完整的 subagent 往返**（9 个 Task 共 10 轮 fix round、25 次顶回），其中相当比例花在文档自洽上。
**代价（必须写明，不许美化）**：**控制者亲验抓不到「控制者自己规定的东西是错的」这一类**——而 Plan 02 的 25 次顶回里**全部 25 次都是这一类**（#151「声称已改而未改」、#156「把可求值讲成会命中」、#154「要求一条结构上不可能变红的测试」）。**独立评审者是唯一能抓到它的席位。**
**缓解措施（三条，都要执行）**：① **实现者的每一处顶回一律先假定成立**，控制者必须**独立重导出**它的依据才能裁定（本 Task 三条都重导出了：`DEFAULT_DB_URL` 亲验确实是 `pe.db`、`Page` 的约束亲验、`tests/` 下 `__init__.py` 数亲验为 0）；② 每个 Task 的派单里**必须逐字写「若你认为本派单某条决定是错的，顶回来」**并给出 Plan 02 的顶回战绩（29/29）；③ **全分支终审照旧派独立评审者**（技能要求的最强模型那一席不省）。
**⚠️ 若某个 Task 的实现者顶回 0 处，控制者要在账本里写明「本 Task 无顶回」并**加倍**亲验**——29/29 的命中率意味着「0 处顶回」更可能是派单太粗、实现者没读出来，而不是计划真的对。

**下一步**：抽 `task-2-brief.md` → 派实现者（7 张表 + 演示数据）。

---

### Task 2: 反馈与预警的 7 张表 + 演示数据 — 预检扫描（Pre-flight，控制者亲跑）

**代码基线**：`a44968f`（Task 1 结案，工作树干净）。**测试基线**：`824 passed`；domain **996/0/288/0/100%**；**18 张表**；扫描面 **38**。
**取证脚本**：`t2_probes/_preflight.py`（一份，Ruling 1 的口径）。

#### Ruling 6 — 预检查出 1 Critical / 3 Important / 2 Minor，计划正文更正 7 处

**P3-A1（Critical）是本轮唯一但最重的一条：计划把 3 张表放进 `models/ops.py`，照做会当场撞红 Ruling 97 那条守卫，而唯一的「修法」正是 Ruling 97 逐字禁止的那一个。**

实测机制：`models/__init__.py` 对 **`ops.py` 是 `from .ops import *`（星号导入）**，而对 `feedback.py` 与 `prescription.py` 是 **`from . import feedback, prescription`（非星号）**。故：
- 放进 `ops.py` 的 `Alert` / `Notification` / `WeeklyClassReport` 三个类名会**自动进入 `models` 的公有命名空间** → `assert observed - _MODELS_SUBMODULES == set(_MODELS_PUBLIC_BASELINE)` 红（多出 3 个名字）；
- 而消掉这条红的唯一办法是**把 `_MODELS_PUBLIC_BASELINE` 从 33 抬到 36** —— **那正是 Plan 02 的实现者顶回过、控制者采纳过的那条禁令**（Plan 02 账本 Ruling 150 的顶回 1：「往基线里加新名字等于把『拆包没改导入面』偷换成『拆包后的现状』，断言两侧就同源了（硬规矩 #35），而 `…is_unchanged_by_the_split` 这个函数名会当场变成谎话」）。

**裁定：7 张表全部放 `models/feedback.py`，`ops.py` 一张都不加。** 三个理由：① `feedback.py` 走非星号导入，7 个类名**自动**留在公有面之外，**与 Plan 02 的 `prescription.py` 完全同一个机制**，零新增守卫；② **`feedback.py` 自己的 docstring 已经认领了 `weekly_class_report`** —— 逐字写着「打卡记录、RPE、二次小测、**班级周报（`weekly_class_report`，spec §4.7）全部属 Plan 03，由它填充**」，即 **Plan 02 Task 1 建这个空壳时的意图就是 §4.5–§4.7 全归它**，而本计划的作者（控制者）没读那段 docstring 就按 spec 的章节标题分了模块；③ spec 的 §4.5/§4.6/§4.7 分节是**文档结构**、不是 Python 模块布局的约束。

**⚠️ 连带三件事已写进计划**：(a) `feedback.py` 那段「**本模块今天刻意是空的**」的 docstring **必须整段重写**（否则它会说「这里是空的」而文件里有 7 张表），重写时**保留它指向 `prescription.py` docstring 的那句交叉引用**；(b) `_MODELS_SUBMODULES`（六个子模块）与 `_MODELS_PUBLIC_BASELINE`（33）**都不动**；(c) `test_plan02_tables_stay_out_of_the_models_public_namespace` 要**扩到 11 个表类**（Plan 02 的 4 个 + 本计划的 7 个），函数名里的 `plan02` 要不要改成 `plan02_and_03` 由实现者判断并说明理由。

**→ 控制者错误 #4**：分模块时**照着 spec 的章节标题分**，没有先实测 `models/__init__.py` 的导入方式。**这与 Plan 02 的控制者错误 #148 同型**（那次是「只核了 `LastPrescription.microcycle_weeks` 有没有住址，没把 5 个字段逐个对到列上」）——**都是「对着文档的形状推理，没对着代码的实际机制推理」**，而 Plan 02 的 25 次顶回里**每一次**的实现者理由都是这一句。
**→ 补硬规矩 #100：把一个类/函数放进某个既有模块之前，必须先实测那个模块是怎么被重导出的（星号 vs 具名 vs `from . import x`）——「放进哪个文件」在有重导出的包里不是排版问题，是公开面问题。** 依据：P3-A1 / 控制者错误 #4；Plan 02 的 Ruling 97 与 Ruling 150 顶回 1 已经为同一件事付过两次学费，这是第三次。

**其余 5 条**（详见计划正文的预检总表）：
- **P3-A2（Important）**：`test_models.py` 的命中点是**约 11 类**，不是计划抄来的「六处 + 两处」（那是 Plan 02 Task 6 的数）。逐类列进了 Step 0 的表。新值：表数 **25**、`json_text_columns` **14 → 21**、`_BATCH_OWNED_TABLES` **5 → 9**、函数名 `eighteen → twenty_five`；**`_MODELS_PUBLIC_BASELINE` 的 33 刻意不动**（P3-A1）。
- **P3-A3（Important）**：`_BATCH_OWNED_TABLES` **不只住在测试里** —— 实测命中 `app/db/models/__init__.py`、`app/db/models/prescription.py`（两处）、`app/pipeline/daily.py`、`tests/db/test_models.py`（六处）。**它是生产代码里的常量，测试那一份是镜像**；先实测定义在哪个文件（`__init__.py` 那一处可能只是重导出），**两处必须同时改**，否则 `assert observed == _BATCH_OWNED_TABLES` 会红在一个看不懂的地方。
- **P3-A4（Important）**：`weekly_adjustment` 今天**没有任何 `UniqueConstraint`**（实测约束 = `ck_weekly_adjustment_source` + 2 个 FK + `ix_weekly_adjustment_batch_id` 非唯一索引，8 列），故 S2 那条是**全新**的。要有一条测试钉住「同处方 + 同周 + 同原因 + 同来源」插第二次会 `IntegrityError` —— 这是 Review Focus 第 3 条的 **DB 层那一半**（应用层那一半是 Task 7 的 `window_key`）。
- **P3-A5（Minor）**：`_in_domain(column, allowed: Iterable[str], name)` 实测**只吃字符串词表**，而 `ops.py` 里**没有整数区间的先例** → `rpe BETWEEN 0 AND 10` 是本计划第一处手写 CHECK，**必须在类常量上写 `RPE_MIN = 0` / `RPE_MAX = 10`**，否则测试里的 `0` 与 `10` 是两个没有出处的魔数（而 spec §8.2 的「连续 ≥ 9」与「均值 > 7」都建立在这个值域上）。
- **P3-A6（Minor，控制者自查）**：计划写 `feedback.py` 是「475 B 的空壳」——实测 `read_bytes()` **475 B**、`read_text().encode("utf-8")` **467 B**，**差 8 字节 = 8 个 CRLF**，即**这个文件在磁盘上是 CRLF**。数字没错但口径要写明：`backend/app/` 下的 `.py` **混用 CRLF 与 LF**（`.gitattributes` 只钉了 `backend/data/**` 与 `.superpowers/**`），**改它时要保持原有行尾**（`read_bytes()` 量、`newline=""` 写），否则一次编辑会把 8 行行尾全改掉、让 `git diff` 看起来整文件重写。**⚠️ 这是硬规矩 #89 扩写（数行尾用 `read_bytes()`）的又一次现身**——这次它没有导致误判，但差 8 字节这件事本身只有在两个口径都量了才看得见。

**计划正文更正**：`_t2_preflight_patch.py`，**7 处替换全部命中 1 次**（硬规矩 #79）。

**下一步**：抽 `task-2-brief.md` → 派实现者。**按 Ruling 1，目标 0–1 轮。**

---

## ✅ Task 2: complete (commits bcf3936..fd73788, 0 fix round)

**交付**：`d07a252`（Step 0：表数 18→25 的全部命中点先改测试，**刻意红**：4 failed / 790 passed / 1 collection error）、`78fa495`（7 张表全在 `models/feedback.py` + `weekly_adjustment` 唯一约束 + 全部散文同步 → 841 passed）、`fd73788`（`app/demo_data.py` + 4 条测试 → 845 passed）。

**验收（控制者本机亲跑复核，探针 `t2_probes/_verify.py` 已入库；全部 15 项 ✅）**：
- 全量 **824 → 845 passed**（+17 在 `tests/db/test_models.py`：`def test_` 30 → 47；+4 在 `tests/test_demo_data.py`）；带 `--cov` **844 passed, 1 skipped**
- `app/domain/` 四格 **996 / Miss 0 / 288 / BrPart 0 / 100% 逐字未变**（本 Task 不加 domain 代码）✓
- **表数 18 → 25** ✓；`len(json_text_columns)` **14 → 21** ✓；`DATA_TABLES` **11 → 18** ✓；外键 24 → **41**；`_in_domain` 列 18 → **23**
- **P3-A1 落地证据**：`_MODELS_PUBLIC_BASELINE` **仍 33**（两处断言一字未动）、`_MODELS_SUBMODULES` **仍六个**、**7 个新类名进公有面的数量 = 0**、`git diff bcf3936 HEAD -- backend/app/db/models/ops.py` **输出为空（一个字节没改）** ✓；守卫改名 `test_plan02_and_plan03_tables_stay_out_of_the_models_public_namespace` 并扩到 **11 个表类**
- **7 张表的列数与约束逐个亲验**：`class_session` **7** 列 / `uq_class_session_section_date_period`；`rpe_record` **6** / `ck_rpe_record_rpe` + `uq_rpe_record_session_student`；`training_log` **10** / `ck_training_log_feeling` + `uq_training_log_student_day`；`mini_test` **10** / `uq_mini_test_student_semester_week`；`alert` **14** / `ck_alert_level` + `ck_alert_status` + `ck_alert_subject_is_exactly_one` + `uq_alert_rule_subject_semester_window`；`notification` **10** / `ck_notification_recipient_kind` + `ck_notification_channel`；`weekly_class_report` **12** / `uq_weekly_class_report_section_semester_week`
- **`weekly_adjustment` 仍 8 列**（本 Task 只加约束不加列）+ 新 `uq_weekly_adjustment_prescription_week_reason_source`（4 列：`prescription_id` / `week` / `reason` / `source`）✓
- **`notification` 的两个 FK 都带 `ondelete='SET NULL'`**（`alert_id` → `alert.id`、`prescription_id` → `prescription.id`）✓
- **扫描面仍 38** ✓（`app/demo_data.py` 是 `app/` 根下模块，不在 `SCANNED_DIRS` 任何一项里，与 `app/main.py` 同档）
- **P3-A6 落地**：`feedback.py` 现在 **43 360 B / 679 行 / 纯 CRLF**（保持了它原有的行尾，没有一次编辑把 8 行行尾全改掉）；「本模块今天刻意是空的」已消失、星号导入的理由已写进去 ✓
- **禁区**：三个指纹 `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` **逐字不变**、CRLF 均 0；`git diff bcf3936 HEAD -- backend/data` **为空**；`pe.db` **不存在**；`data/seed/` **0 文件**

### Ruling 7 — 实现者顶回 3 处，**全部采纳**（Plan 03 的第 5–7 次顶回；累计 **31 次，31 次都对**）

**顶回 1（Critical，采纳 → 控制者错误 #5）：「`alert` 用 `0` 作哨兵」这个方案在结构上跑不起来。**
计划的原文是「`student_id` 与 `course_section_id` 都改成 `nullable=False` + 用 `0` 作哨兵（学生级预警 `course_section_id = 0`、班级级预警 `student_id = 0`）」，理由是要绕开「SQLite 的 UNIQUE 对 NULL 是 NULL ≠ NULL，两列可空会让去重约束对班级级预警静默失效」。
**实现者用最小复现探针（`p01_sentinel_fk.py`）证明它跑不起来**：那两列**都是外键**，而 `PRAGMA foreign_keys=ON` 的钩子挂在 **`Engine` 类**上（故内存库与磁盘库都生效），父表 `student` / `course_section` **没有 `id = 0` 的行** → **每一条哨兵行当场 `FOREIGN KEY constraint failed`**。
⚠️ **更严重的是它的失效时机**：照派单做的话，**本 Task 一条测试都抓不到**（本 Task 不写 `alert` 行），缺陷要到 **Task 7 第一次真的落一条预警**时才爆 —— 而那已经是三个 Task 之后。
**实现者的替代设计（控制者亲验已落地）**：两列**保持可空**，**新增一个 NOT NULL 的 `subject_key: VARCHAR(24)`** 承担去重键的「主语位」（形如 `"student:123"` / `"class:45"`），去重键从 5 列降到 **4 列**（`rule_id` / `subject_key` / `semester_id` / `window_key`），并加 **`ck_alert_subject_is_exactly_one`**（`student_id` 与 `course_section_id` **恰好一个非空**）把「两列都可空」重新收紧。**这与 `CleaningLog` 的 `student_no` / `student_id` 双列承载 Ruling 25 是同一形状**（一个 NOT NULL 的逻辑主语 + 一个可空的 FK），即**本仓已有的先例**。并留了反证测试。
**→ 补硬规矩 #101：用哨兵值（`0` / `""` / `-1`）代替 NULL 之前，必须先确认那一列不是外键 —— 或者父表真的有那一行。** 依据：控制者错误 #5。**⚠️ 这一族与硬规矩 #92（要求一条测试变红前先论证破坏在结构上可达）是同一件事的两面**：#92 管「守卫能不能红」，#101 管「数据能不能写进去」，**两者都是「先论证结构上可行，再写进计划」**。

**顶回 2（采纳）**：`class_session` **需要一条 `UniqueConstraint(course_section_id, session_date, period)`**，而计划给另外 5 张表都点了唯一约束、**唯独漏了它**。理由成立：`repo.upsert` 是「先 select 再写」，没有 DB 兜底会炸在读侧的 `MultipleResultsFound`；而且 **`class_session` 不能进 `_replay_cleanup`**（`rpe_record.class_session_id` 是 **NOT NULL 外键**、而 `rpe_record` 是**用户实时写入**的，重放不该删掉学生刚交的快评）→ **upsert 是它唯一的幂等手段**。
**⚠️ 这条连带传导给 Task 8**（实现者已把它写进 `feedback.py` / `repo.py` / `daily.py` 三处）：**`ClassSession` 有 `batch_id` 但不得进 `_replay_cleanup`**。→ 故 `_BATCH_OWNED_TABLES` 的 9 张与 `_replay_cleanup` 的清单**不是同一份**：前者是「有 `batch_id` 列的表」，后者是「重放时按批删的表」。**这个区分要在 Task 7/8 的正文里写明**，否则下一个人会以为两个清单该一样。

**顶回 3（采纳）**：**`notification.prescription_id` 也要 `ondelete="SET NULL"`**，派单只点了 `alert_id`。理由成立且更紧急：**`prescription` 今天就已经在 `_replay_cleanup` 里**（Plan 02 Task 7 加的），少了这一个 `ondelete`，**第一条指向处方的通知落库后、下一次重放同一天就炸在 `delete_by_batch` 上**。控制者亲验两个 FK 都带 `SET NULL` ✓。

### 控制者错误 #6 —— P3-A3 的「两份」是假的

预检的 P3-A3 逐字写着「`_BATCH_OWNED_TABLES` **不只住在测试里** —— 实测命中 `app/db/models/__init__.py`、`app/db/models/prescription.py`（两处）、`app/pipeline/daily.py`、`tests/db/test_models.py`（六处）。**它是生产代码里的常量，测试那一份是镜像**」。
**实现者用 AST 取证（`p03_batch_owned.py`）证明它只有一份定义**（`tests/db/test_models.py`），**`app/` 下那 8 处全是散文引用、没有一处赋值** → **不存在「生产代码常量 + 测试镜像」，没有第二份可改**。那 8 处「五张」的说法已全改成「九张」。
**⚠️ 这与 Plan 02 的控制者错误 #155 是同一形状**（用文本命中数当成「定义的份数」）—— **#155 是「正则数表格行漏了加粗编号」，本次是「grep 命中数把散文引用当成了定义」**。两者都是硬规矩 #89 要防的事，而 #89 的正文只说了「数键/字段/成员」，**没说「数定义」**。
**→ 硬规矩 #89 再扩写：数「一个名字有几份定义」时，用 AST（`ast.parse` 后找 `ast.Assign` / `ast.AnnAssign` 的 target），不要用文本命中数——散文引用、注释、docstring 里的同名提及都会被算进去。**

### 11 处偏离派单字面：全部追认

除上面 3 处顶回外另 8 处：① P3-A3 无第二份可改（见 #6）；② 守卫改名（理由成立：本条守的是「每一批新表都按子模块引用」，名字只写一个计划会让下一个计划另起第三条同型守卫）；③ **`mini_test` 是 10 列不是 11**（被它自己写的形状测试当场抓出）；④ **多改 6 个派单没列的文件**（全是硬规矩 #66 的散文同步，含 `_shared.py` / `prescription.py` 那「三处同一事实」的 14 → 21）；⑤ `tests/api/test_scope.py` 实测**不依赖表数**故未改（只改了 `conftest.py` 两处散文）；⑥ `DemoReport` 字段形状自定；⑦ 多写一条 demo 测试（`test_demo_feedback_gives_the_alert_engine_something_to_fire_on`）；⑧ **派单 0.1(a) 自相矛盾**（「必须整段重写」与「保留那句交叉引用」两句打冲突）**按后半句办** —— 即重写整段、但不保留那句已不适用的交叉引用，改成说明为什么 7 张表都住在这里。**⚠️ 这是本计划自审（Ruling 3）漏掉的第 7 处自相矛盾，由实现者抓出。**

### `demo_data` 的口径与一条额外的变异取证

四条测试：`test_build_demo_feedback_is_idempotent`（**跑三次逐字不变** 16 / 480 / 1680 / 480，**计数是从库里数出来的、不是自报**）、`test_demo_data_never_touches_the_clock`（**词表从 `tests/seed/test_generate.py` import、不抄第二份** + 4 组自证 + 1 组负对照）、`test_seed_database_still_writes_no_feedback_rows`（**这条守的是 P3-A1 的分区决定**）、`test_demo_feedback_gives_the_alert_engine_something_to_fire_on`。
**实现者自跑了一条变异**（Ruling 1 说本 Task 不要求变异，它自己加了）：把 `_training_logs` 的 upsert 换成裸 `add` → 幂等那条当场红，还原后 sha256 逐字一致。**这是「新守卫有牙」的自证，控制者采纳。**

### 待清扫：**11 条**（推 Task 9），Critical 级遗留 **0** 处

最要紧的两条：① **`ops.py` 的 docstring 仍写「`alert` / `notification` 属计划 03」**（按 P3-A1 的要求它**0 字节未改**，而 `feedback.py` 与 `models/__init__.py` 两处已显式纠正 → **三份文档里有一份是旧的**）；② **`backend/pe_demo.db` 是 Task 1 留下的陈旧演示库（18 张表）** —— 下次跑 uvicorn 时 `create_all` 会补出 7 张新表，但**不会**给已存在的 `weekly_adjustment` 补那条新唯一约束，**演示库上那道 DB 兜底会静默缺席**。实现者没删（那是控制者的产物）→ **控制者本轮已删掉**（`pe_demo.db` 172 032 B / 18 张表 → 已删，下次跑 uvicorn 会按 25 张表重建）。**⚠️ 这也是一条通用教训：演示库是「不可复现的产物」，与 `pe.db` 禁区的性质相同，只是它可重建故不进禁区清单。→ 记进 Task 9 的 `demo.ps1` 要求：脚本第一步必须删掉旧的 `pe_demo.db`。**

### ⚠️ 按硬规矩 #86 回扫 Task 6/7/8（本 Task 结案改变了它们的前提）

1. **Task 6**：`StudentHit` / `ClassHit` 除了 `window_key` **还必须产出 `subject_key`**（形如 `"student:<id>"` / `"class:<id>"`，`VARCHAR(24)`）—— 它是 `uq_alert_rule_subject_semester_window` 的四列之一，而**去重键已经从 5 列变成 4 列**（`rule_id` / `subject_key` / `semester_id` / `window_key`）。计划 Task 6 的正文写的还是 5 列（含 `student_id` 与 `course_section_id`），**Task 6 预检时必须更正**。
2. **Task 7**：`alert_stage` 落 `alert` 行时要填 `subject_key`，且 **`ck_alert_subject_is_exactly_one`** 要求 `student_id` 与 `course_section_id` **恰好一个非空** —— 学生级预警填 `student_id`、班级级填 `course_section_id`，**不能两个都填、也不能两个都不填**。
3. **Task 8**：`_replay_cleanup` 的清单**不含 `class_session`**（顶回 2 的连带），故 `_BATCH_OWNED_TABLES`（9 张，「有 `batch_id` 列的表」）与 `_replay_cleanup` 的清单（**8 张**：Plan 02 的 5 张 + `alert` + `weekly_class_report` + …**Task 7/8 落地时自己数**）**不是同一份**。这个区分要写进 `daily.py` 的 docstring。
4. **Task 9**：`demo.ps1` 的第一步必须删掉旧的 `pe_demo.db`（待清扫第 2 条）。

**下一步**：抽 `task-3-brief.md` → 派实现者（泛型 CRUD 工厂 + 23 个资源）。

---

### Task 3: 泛型 CRUD 工厂 + 23 个资源 — 预检扫描（Pre-flight，控制者亲跑）

**代码基线**：`8d8d3b3`（Task 2 结案，工作树干净）。**测试基线**：`845 passed`；domain **996/0/288/0/100%**；**25 张表**；扫描面 **38**。
**取证脚本**：`t3_probes/_preflight.py`（一份，Ruling 1 的口径；**全部运行时口径**：`Base.registry.mappers` 找模型类、`__table__.constraints` 找唯一约束、`isinstance(c.type, JsonText)` 找大 JSON 列、`__table__.foreign_keys` 找出向外键）。

#### Ruling 8 — 预检查出 1 Critical / 4 Important / 3 Minor，计划正文更正 6 处

| # | 级别 | 实测事实 | 处置 |
|---|---|---|---|
| **P3-B1** | **Critical** | **23 个资源里有 11 个的模型类不在 `app.db.models` 的公有导入面上**（Ruling 97）。实测：`exercise` / `prescription_template` / `prescription` / `weekly_adjustment` 住 `app.db.models.prescription`；`class_session` / `rpe_record` / `training_log` / `mini_test` / `alert` / `notification` / `weekly_class_report` 住 `app.db.models.feedback`。**计划 Task 3 的正文一个字都没提** —— 照字面写 `model=models.Prescription` 会得到 **11 个 `AttributeError`**。 | 计划正文插入一张 **23 行的表**，逐个给出「资源路径 / 表名 / 模型类 / **import 路径** / 列数 / 自然键 / `JsonText` 列」。**⚠️ 这是 Ruling 97 第三次没被传导**（前两次：Plan 02 的 P6-A8 与 Plan 03 Task 2 的 P3-A1）→ **补硬规矩 #102** |
| **P3-B2** | Important | **3 个资源没有唯一约束**：`course_section`、`fitness_test_batch`、`notification`。故 `test_create_with_a_duplicate_natural_key_is_409` **对它们写不出来**，`repo.upsert` 的 `key_fields` **也没有东西可填**。 | `build_crud_router` 加 **`natural_key: tuple[str, ...] | None`**：非空 → POST 走 `repo.upsert`（撞键 409）；`None` → POST 走**裸 `session.add`**（**结构上不可能撞键，故没有 409 这一档**）。**⚠️ 那条 409 测试只对 20 个有自然键的资源写，并对 3 个没有的写一条反向测试**（`test_a_resource_without_a_natural_key_never_returns_409`）—— 否则下一个人会以为 409 是普适的。**这是硬规矩 #92 的正面执行**（先论证破坏在结构上可达，再要求测试变红） |
| **P3-B3** | Important | **`JsonText` 列实测共 21 个、分布在 8 张表**（`interest_survey` 2、`derived_metrics` 3、`stratification_result` 1、`exercise` 1、`prescription` **5**、`mini_test` 1、`alert` 1、`weekly_class_report` **5**）。计划要求 `list_exclude` 由调用方**逐个手写** → 23 行里手抄 21 个列名，**抄漏一个就是一次全表 JSON 拉取**（Plan 02 Task 7 的性能回归正是「大 JSON 列 eager 加载」，`elapsed` 一度到 **115 s**）。 | **`list_exclude` 改成自动探测**：缺省 `None` = `[c.name for c in model.__table__.columns if isinstance(c.type, JsonText)]`，保留显式覆盖参数。**理由：自动探测不会抄漏，而「多排除一列」的后果（read-one 里还能拿到）远轻于「少排除一列」（性能回归且没人看得见）。** 要有一条测试遍历 23 个资源、断言 **list 响应里一个 `JsonText` 列都不出现**、read-one 响应里全部出现 |
| **P3-B4** | Important | `on_delete="restrict"` 要「点名是哪张子表挡住的」，而**子表清单不在模型上**：实测 `model.__table__.foreign_keys` 给的是**出向**外键（父表），**入向**（谁指向我）要扫 `Base.metadata` 全部表。 | `crud.py` 里写 `_child_tables(model) -> list[tuple[str, str]]`（遍历 `Base.metadata.tables` 找 `fk.column.table is model.__table__`）。**⚠️ 必须排除 `ondelete` 为 `SET NULL` / `CASCADE` 的 FK** —— 实测 `notification.alert_id` 与 `notification.prescription_id` 都带 `ondelete="SET NULL"`（Task 2 顶回 3 加的），**不排除就会把 `notification` 误报成「挡住删除 `alert` 的子表」**，而它根本不会挡（DB 自己 SET NULL）。要有一条测试钉住这个排除 |
| **P3-B5** | Important | **5 张表的唯一约束是无名的**（`semester.name` / `teacher.staff_no` / `student.student_no` / `exercise.ref` / `prescription_template.template_ref`，实测 `UniqueConstraint.name is None`）。 | **409 的消息不得引用约束名**（它是 `None`，会渲染成字面 `"None"`）→ **引用列名**。要有一条测试断言 409 的 `message` 含列名、**不含字面 `"None"`**（否则前端会把 `None` 显示给教师看） |
| P3-B6 | Minor | `app/api/deps.py` 的公开面实测 = `Engine` / `Page` / `Student` / `current_student` / `current_teacher` / `get_db` / `require_scope`，**没有模块级大写常量**；`DB_URL_ENV_VAR` 与 `DEMO_DB_URL` 住在 **`app/main.py`**。`errors.py` = `error_response(status_code, code, message, detail=None, headers=None)` + `register_error_handlers(app)`。 | 计划正文的出处写错了，已更正。**工厂不碰这两个常量**（它只拿 `Session`），故不改设计 |
| P3-B7 | Minor | `repo.py` 的公开函数**只有两个**：`upsert(session, model, key_fields: Sequence[str], values: dict) -> Any` 与 `delete_by_batch(session, model, batch_id: int) -> int`。**没有 `get_or_404` 之类的读取助手。** | read-one 自己写 `session.get(model, pk)` + `if obj is None: raise HTTPException(404)`。**不要为此给 `repo.py` 加新函数**（它是 Plan 01 的模块，加函数要同步公开面基线；而 `session.get` 是 SQLAlchemy 原生 API，不需要包装） |
| P3-B8 | Minor | **`alert` 与 `notification` 的 `on_delete` 定成 `restrict` 是错的**：`alert` 是「哪个学生被标记过」的**审计记录**（RCT 的过程数据），`notification` 是**学生看到的消息历史**。`restrict` 意味着「没有子行时可以从 API 删掉」—— 那会静默抹掉研究数据。 | **两个都改成 `forbid`（405）**，理由与 `stratification_result` 一样：**删它们的正确方式是重放（`_replay_cleanup` 按 `batch_id` 删），不是从 API 单点删。** ⚠️ 读写矩阵的三个计数随之变成 **可写 8 / 只读 15；`restrict` 11 / `forbid` 11 / `cascade` 1**（原为 12/10/1），**那条遍历 `RESOURCES` 计数的测试要用新数** |

**→ 补硬规矩 #102：一条纪律（如 Ruling 97 的「新表类不进 `models` 公有面」）一旦立下，就必须写进计划的 Global Constraints，而不是只写进当时那个 Task 的正文——因为后续每个 Task 的预检都要靠 Global Constraints 那一节来提醒控制者。** 依据：P3-B1 是 Ruling 97 **第三次**没被传导（前两次：Plan 02 的 P6-A8「`_replay_cleanup` 不能用 `models.Prescription`」、Plan 03 Task 2 的 P3-A1「`ops.py` 是星号导入」）。**三次都是控制者在写新 Task 时忘了它，而三次都要靠预检或实现者顶回来才发现。**
⚠️ **本计划的 Global Constraints 里其实已经写了 Ruling 97 那一条**（逐字有「**一律走子模块路径**：`from app.db.models.feedback import ClassSession`」）—— **而 Task 3 的正文没有把它落到 23 个资源上**。故 #102 的完整形态是：**写进 Global Constraints 只是第一步，每个 Task 的正文还要把它落成「本 Task 的每一处具体决定」；抽象的纪律不会自己应用到具体的清单上。**

**计划正文更正**：`_t3_preflight_patch.py`，**6 处替换全部命中 1 次**（硬规矩 #79）。

**下一步**：抽 `task-3-brief.md` → 派实现者。**⚠️ 本 Task 是 Plan 03 代码量最大的一个**（一个泛型工厂 + 23 个资源的声明 + 4 个 schema 模块），**控制者预期 1 轮 fix round。**

---

## ✅ Task 3: complete (commits 40a7a0e..e88afaf, 0 fix round)

**交付**：`51b5b19`（泛型工厂 `crud.py` + `schemas/{__init__,_base,organisation,derived}` + `routers/{__init__,catalog}` 先落 4 个资源 + `main.py` include + 批次 A 12 条测试，845→857）、`dabc3ef`（余下 4 个 schema 模块）、`7fa8ecf`（`catalog.py` 扩到 23 行 `RESOURCES` + 批次 B 17 条遍历型守卫，857→874）、`9a62a93`（`upsert` 回滚守卫 + `readable`/`list_exclude` 覆盖两条守卫，874→**876**）、`e88afaf`（报告）。

**验收（控制者本机亲跑复核，探针 `t3_probes/_verify.py` 已入库）**：
- 全量 **845 → 876 passed**（+31，**既有 845 条零退步**）；带 `--cov` **875 passed, 1 skipped**
- `app/domain/` 四格 **996 / Miss 0 / 288 / BrPart 0 / 100% 逐字未变** ✓
- **扫描面 38 → 49**（pipeline 8 + db 11 + domain 16 + **api 14**；api 从 3 涨到 14 = `crud` 1 + `schemas` 8 + `routers` 2 + Task 1 的 3）。**守卫下界 `>= 18` 未改仍绿**（Task 1 的 S6 裁定兑现了）
- 表数 **25**（未建表）；`_MODELS_PUBLIC_BASELINE` **33 未动**（`dir(models)` 公有名 39 = 33 + 6 个子模块）
- **端点计数走 `/openapi.json`**：47 个路径全在 `/api/` 下，**POST 9 / PATCH 9 / DELETE 8**，23 个资源逐名核对**一个不缺、一个不多**
- **11 个子模块 import 全部走对**：运行时 `__module__` + `hasattr(models, X) is False` + **AST 两条 `ImportFrom` 逐名对拍**三面钉住；控制者亲验「11 个表类进 `models` 公有面的数量 = **0**」
- **P3-B3 的两套口径控制者独立复核全部吻合**：全库 `JsonText` 列 **21** 个 / **9** 张表（多出的是 `cleaning_log`，它不是资源）；**23 个资源上是 19 个 / 8 张表**
- **禁区**：三个指纹逐字不变、`git diff 40a7a0e HEAD -- backend/data` 为空、`pe.db` 与 `pe_demo.db` 都不存在、`data/seed/` 0 文件、21 个 YAML 的 CRLF 全 0

**⚠️ 一个框架事实（实现者报的，控制者亲验坐实，值得记账）**：**FastAPI 0.141.1 的 `include_router` 是惰性的**（塞一个 `_IncludedRouter` 包装对象）—— 控制者实测 `len(create_app().routes) == 6`，而 `/openapi.json` 的 `paths` 是 **47**。**「注册了多少端点」不能用 `len(app.routes)` 数，必须走 `/openapi.json`。** 本 Task 的所有端点计数都是 OpenAPI 口径。

### Ruling 9 — 实现者顶回 7 处，**全部采纳**（Plan 03 的第 8–14 次顶回；累计 **38 次，38 次都对**）

**顶回 1（采纳）**：派单的 Files 清单只给了 4 个 schema 模块（`organisation` / `assessment` / `derived` / `prescription`），而 **7 个 feedback/alert 资源的 schema 在里面没有住址** → 实现者按 File Structure 补建 `schemas/feedback.py` + `schemas/alerts.py`，另加 `_base.py`（先例是 `app/db/models/_shared.py`）。**⚠️ 这是硬规矩 #97 的形状**（派单里提到的每一个文件都要先核实它够不够用），而 #97 只覆盖了「既有守卫」这一半，没覆盖「要新建的文件清单」。

**顶回 2（采纳 → 控制者错误 #7）**：**读写矩阵的三个计数，派单两个数都错。** 派单说「可写 8 / 只读 15；`restrict` 12 / `forbid` 10 / `cascade` 1」，并在 P3-B8 里说「原为 12/10/1 → 更正后 11/11/1」。**实现者从矩阵逐行数出来的实测是：可写 9 / 只读 14；`restrict` 12 / `forbid` 10 / `cascade` 1**，且指出 **P3-B8 那句的两个数都对不上**（更正前应是 **14/8/1** —— 控制者把「挪 2 行」算成了「挪 1 行」）。**更讽刺的是：矩阵正文自己就写着「数字自己数、不要照抄本行」（硬规矩 #44），而控制者在写 P3-B8 时照抄了自己算错的数。** 控制者用 OpenAPI 口径独立复核：POST 9 / PATCH 9 / DELETE 8，与实现者的三个独立口径（`RESOURCES` 逐行计数、OpenAPI 方法计数、detail 路径方法组合分布 `{get:14, get+patch+delete:8, get+patch:1}`）**全部吻合**。

**顶回 3（采纳 → 控制者错误 #8）**：**P3-B3 混用了两套口径。** 派单说「`JsonText` 列实测共 21 个，分布在 8 张表」——**21 是全库总数、分布在 9 张表**（多出 `cleaning_log` 的 2 列，而它不是资源）；**23 个资源上是 19 个 / 8 张表**。控制者独立复核两套数全部吻合（21/9 与 19/8）。**⚠️ 这是「一个数在两个范围内都成立、但含义不同」的经典形状**，与 Plan 02 的控制者错误 #131（「待改文件表一行混两个口径」）同族。

**顶回 4（采纳 → 控制者错误 #9）**：**P3-B2 要求的 409 测试范围结构上不可达。** 派单说「那条 409 测试只对 20 个有自然键的资源写，并对 3 个没有的资源写一条反向测试」—— 而 **20 个有键资源里 13 个是只读的（POST → 405）**，故 HTTP 面只能验 **7** 个；反向的 3 个里 `notifications` 也是只读，只能验 **2** 个。实现者的处置：**HTTP 面 7+2、结构面遍历全部 20/3**。**⚠️ 这是硬规矩 #92 的第 4 次同型**（要求一条测试覆盖一个结构上不可达的范围；前三次：Plan 02 的 P6-A1、控制者错误 #150、#154）。

**顶回 5（Critical，采纳 → 控制者错误 #10）**：**`repo.upsert` 撞键时不抛异常——它更新并返回。** 故派单要求的「POST 走 `repo.upsert`」与「撞键 → 409」**不能同时成立**。实现者的处置：用 **`obj not in session.new`** 判定撞键 + **`rollback()`**。⚠️ **`rollback()` 这一拍是 commit ④ 才补上的，而它是本 Task 最要紧的一处**：**不回滚则一次被拒的 POST 会静默改掉已有行** —— 那是「返回 409 但数据已经被改了」，比直接 500 危险得多（客户端会以为什么都没发生）。**并加了一条守卫测试钉住它。**

**顶回 6（采纳）**：派单 Step 1 列的三条错误映射测试（`ValueError`→422 / `IntegrityError`→409 / 未处理→500）**已由 Task 1 交付在 `tests/test_main.py`** → **不重复**（第二个所有者，硬规矩 #35 的同族）。

**顶回 7（采纳 → 控制者错误 #11）**：派单 Step 1 用 `semester` 测 `DELETE → 204`，而**矩阵给 `semester` 的是 `forbid`** → **那条测试写不出来**。实现者改用 `teachers`，并**另加一条钉住「`writable` 与 `on_delete` 是两个独立开关」**（一个资源可以 `writable=True` 而 `on_delete="forbid"`）。**⚠️ 与顶回 4 同族（第 5 次）：派单要求的东西与自己另一处的决定冲突。**

### 8 处偏离派单字面：全部追认

① 多建 3 个文件（顶回 1）；② **工厂加了 2 道派单没要求的配置校验**（其中「路径必须以 `/api/` 开头」那条**落地当天就抓到实现者自己一次**）；③ 3 处枚举列加 Pydantic 校验（**422 而不是 DB 的 409**，词表仍读模型类常量 → 单一所有者没破）；④ **list 端点不用 `response_model`** —— 理由成立且重要：**否则序列化阶段的 `getattr` 会把 `defer()` 打穿成 N+1，P3-B3 的收益归零**；代价是 OpenAPI 里 list 响应的 schema 为空，**已写进 docstring**；⑤ 不加 `?order_by=` 查询参数（YAGNI，`order_by` 由 `RESOURCES` 声明）；⑥ commit 分 4 个且让 `catalog.py` 从 ① 起就是唯一所有者；⑦ `scope` 只挂三个单行端点、且身份头**条件注册**（只读资源不要求身份头，否则大屏的匿名读会被 401 挡掉）；⑧ 批次 C 两条测试是派单没点名的。

### 变异自证 3 条（Ruling 1 说本 Task 不要求变异，实现者自己加了；控制者采纳）

① `_child_tables` 不排除 `SET NULL` → 报 `assert [('notification','alert_id')] == []`；② `list_exclude` 自动探测改成 `()` → 两条 `JsonText` 守卫一起红；③ `model_dump(exclude_unset=False)` → PATCH 测试红成 `409 NOT NULL constraint failed`。**三条都已还原，`grep MUTATION` 零残留。**

### 待清扫：**6 条**（全无 Critical），其中两条是**前序遗留**

① `app/db/session.py` 的 docstring 仍写「15 张表」；② `app/db/repo.py` 的 `upsert` docstring 仍写「对 14 个模型通用」；③ `_seed_one_row_per_table`（24 表手写字面量，若第三个 Task 也要用就该提到 `conftest`）；④⑤⑥ 见报告 ⑦.4。**⚠️ ①② 是 Plan 01/02 留下的、被本计划的表数增长证伪的散文** —— 与硬规矩 #97 同族（一个改动会让别处的事实过期）。

### 关切 9 条，最要紧的一条要传导给 Plan 04

**`class_session.batch_id` 是 NOT NULL 外键、指向 `daily_sync_run`，而 `daily_sync_run` 不是 23 个资源之一** → **前端拿不到批次列表，故无法用 `batch_id` 过滤课次**。控制者裁定：**本计划不把 `daily_sync_run` 加进 `RESOURCES`**（它是运维表、不是业务实体，教师不该在 CRUD 界面里改它），**改为在 Task 8 的 `class-sessions` list 端点上支持 `?course_section_id=` 与 `?session_date=` 过滤**（前端真正需要的是这两个维度）。**→ 这条已按硬规矩 #86 记进 Task 8 的传导清单。**

### ⚠️ 控制者错误 #12（本轮亲验时新犯，自查出）

控制者的亲验探针用**文本计数**去核 `catalog.py` 的读写矩阵（`cat.count('writable=False')` / `cat.count('on_delete="restrict"')` / `cat.count('build_crud_router(')`），实测得到 **0 / 0 / 1** —— 而实现者报的是 14 / 12 / 23。**原因是 `RESOURCES` 是一张数据驱动的表（一个列表），不是 23 处字面的 `build_crud_router(...)` 调用**，故文本计数天然数不到。
**这正是硬规矩 #89 逐字禁止的动作**（「数键/字段/成员一律用运行时口径，绝不用正则数源码」），而控制者**在同一个探针里同时用了两种口径**：OpenAPI 的运行时计数（对的，与实现者吻合）与文本计数（错的）。**→ 硬规矩 #89 第 5 次被违反（#139 / #147 / #155 / #6 / #12）。**
**处置**：**以 OpenAPI 口径为准**（POST 9 / PATCH 9 / DELETE 8，控制者独立跑出，与实现者的三个口径全部吻合），**文本计数的那三行结论作废、不写进任何裁定**。
**→ 补硬规矩 #103：一个探针里若同时有两种口径能回答同一个问题，以「运行时/结构化」那一种为准，并把另一种的输出**标注为不可用**而不是并列打印——并列打印会让读数的人（包括控制者自己）随手引用错的那一个。** 依据：#12。

**下一步**：抽 `task-4-brief.md` → 派实现者（处方侧的特例端点）。

---

### 插曲：控制者起了 uvicorn 并用真实 HTTP 打了一整圈 CRUD（用户要求「先起服务看看 CRUD 层」）

**取证脚本**：`t3_probes/_live_smoke.py`（用 `httpx` 打 `http://127.0.0.1:8000`，**不是 `TestClient`**——是真实的 uvicorn 进程 + 真实的 `pe_demo.db`）。

**全部符合预期**：`/api/health` → `{"status":"ok","tables":25,"students":0}`；`POST /api/semesters` → **201** + `Location: /api/semesters/1`；撞同名 → **409** `"semester 已经存在同一组自然键（name）的行"`；`GET list` → `{"items":[…],"total":1,"limit":50,"offset":0}`；`PATCH {"weeks":18}` → **200** 且 **`name` 原样保留**（部分更新语义对）；`PATCH {"start_date": null}` → **409** `"NOT NULL constraint failed: semester.start_date"`（**`null` 与「没传」确实可区分**）；`DELETE /api/semesters/1` → **405**（`on_delete=forbid`）；`POST /api/teachers` → 201、`DELETE` → **204**、`GET` → **404** `"teacher 里没有主键为 1 的行"`（`restrict` 在无子行时放行 ✓）；`POST /api/stratification-results` → **405**（只读）；OpenAPI **3.1.0 / 47 paths / 43 schemas / 2xx 响应 65 带 schema（其余 8 个是 204 无响应体，正确）**；CORS 预检（模拟 Vite `localhost:5173`）→ **200** 且 `allow-headers` 回显了 `X-Student-Id`。

**⚠️ 控制者错误 #13（本次冒烟的第一版脚本）**：`POST /api/semesters` 的 payload 只给了 `name`，而 `SemesterCreate` 的必填字段是 `name` / `start_date` / `end_date` / `weeks` → 得到 422，**而控制者当场把它读成「POST 不工作」**。第二版脚本改成**先从 `/openapi.json` 读 `SemesterCreate` 的 `required`、再构造 payload**，一圈全绿。**教训与硬规矩 #89 同族：不要凭记忆构造输入，从运行时读契约。**

### 查出的 3 个前后端对接缺口（用户 2026-10-08 明确要求「要确保后端和前端能够对接的上」）

1. **`X-Student-Id` / `X-Teacher-Staff-No` 在 OpenAPI 里一个都没声明**（`components.securitySchemes` 不存在、spec 顶层无 `security`、47 个路径的 header 参数为空）。**后果：Swagger UI 上没有地方能填它们、生成的 TS 客户端也不知道要发** → 前端一接就撞 401 且不知道为什么。**成因**：Task 3 的偏离 ⑦ 把 `scope` 只挂在三个单行端点上，而那三个端点是 **Task 4** 才建的 → 今天没有任何路由用到身份头。**归 Task 4 修**（它建第一个 `scope` 端点）。
2. **`access-control-allow-credentials` 为 `None`**（`allow_origins=["*"]` 与 `allow_credentials=True` 被浏览器规范禁止并存）。**原型阶段不修**（`main.py` 的 docstring 已明写「上线前两者都要收紧」），但**必须传导给 Plan 04：前端不得用 cookie / `fetch(..., {credentials:'include'})`，身份只能走请求头**。
3. **23 个 detail 路径的参数名全是泛型的 `pk_value`**（`/api/semesters/{pk_value}`），而 `build_crud_router` 只有 `pk: str = 'id'`（DB 列名）、**没有给 OpenAPI 路径参数另起名的口子**。**后果：生成的 TS 客户端里到处是 `pkValue` 而不是 `semesterId`。**

---

### Task 4: 处方侧的特例端点 — 预检扫描（Pre-flight，控制者亲跑）

**代码基线**：`e2a0803`。**测试基线**：`876 passed`；domain **996/0/288/0/100%**；**25 张表**；扫描面 **49**；**47 个端点在线**。

#### Ruling 10 — 预检查出 1 Critical / 4 Important / 1 Minor（含上面 3 个对接缺口），计划正文更正 6 处

| # | 级别 | 实测事实 | 处置 |
|---|---|---|---|
| **P4-A1** | **Critical** | **`WeeklySheet` 不能直接 JSON 化**：`json.dumps(dataclasses.asdict(sheet))` 抛 **`TypeError: cannot pickle 'mappingproxy' object`**（`AssembledBlock.structure` 是只读映射，`asdict` 会 `deepcopy` 它）。**带不带 `default=str` 都失败**——`default` 只在「未知类型」时被调用，而 `asdict` 在**到达 json 之前**就炸了。 | **不许用 `dataclasses.asdict`**。**Plan 02 已经解决过同一个问题**：`prescription_stage.training_package_payload(pkg) -> dict` 就是「`TrainingPackage` → 可 JSON 的 dict」的投影，且已在 `__all__` 里。**weekly-sheet 的投影必须建立在它之上**：把它的 **block 级投影提成模块级函数**（如 `_block_payload`），两处共用。**⚠️ 是「提取」不是「复制」**——复制会产生第二个所有者，而两个投影一旦漂移，前端在学生端看到的 block 与教师端看到的就不是同一个形状。**要有一条测试钉住「两边的 block 逐字段同形」** |
| **P4-A2** | Important | **`weekly_factors_of` 已经存在**（Plan 02 Task 8 交付）：`weekly_factors_of(session, prescription_id: int) -> list[WeeklyFactor]`，在 `prescription_stage.__all__` 里。`WeeklyFactor` 4 个字段 = `week:int / factor:float / reason:str / source:str` | 计划 Task 8 说要「加 `weekly_factors_of`」是**过期的**。**Task 4 直接调用**，Task 8 只消费。⚠️ **硬规矩 #91**（派单里提到的每一条既有能力先核实它存在）—— 本次是**它的正面案例**：预检核实了，故没派一件已经做完的活 |
| **P4-A3** | Important | **`OverrideRecord` 的 7 个字段全部无缺省**；`OverrideKind` 5 个值实测 = `weekly_frequency` / `substitute_exercise` / `intensity_step` / `volume_scale` / `pause`（**下划线不是连字符**）；`apply_overrides(pkg, records, *, exercises)` —— **`exercises` 关键字必填**（Plan 02 的顶回 2） | **请求模型必须是 5 字段的另一个 Pydantic 类**，`teacher_staff_no` 从身份头填、`applied_at` 从服务端时钟填（**让客户端传等于让它能冒充别的教师、还能伪造时间**）。`kind` 的值域**直接引 `OverrideKind`**、不抄第二份字符串。调 `apply_overrides` **必须传 `exercises=`**，否则 `SUBSTITUTE_EXERCISE` 会留下旧动作的视频 URL —— Plan 02 顶回 2 逐字说的「一个看起来正常的谎」 |
| **P4-A4** | Important | `prescription` 实测 **16 列**（含 `label_at_generation VARCHAR(20) NOT NULL`，Plan 02 Task 7 fr1 加的），`teacher_overrides` 是 **`TEXT NOT NULL`** 的 `JsonText` | 「追加一条覆盖」= **读 JSON 列表 → append → 写回**，不是 INSERT。列是 NOT NULL → 空列表写 `[]` 不写 `NULL`。**顺序承重**（Plan 02 的 5.4：多条覆盖同一目标由**列表顺序**决定、后者胜）→ **不要按 `applied_at` 重排序** |
| **P4-A5** | Important | 对接缺口 1（见上） | **本 Task 建第一个 `scope` 端点时把两个身份头注册成 OpenAPI 的 `apiKey` securityScheme**（`in: header`），需要它们的端点挂 `dependencies=[Security(...)]` |
| **P4-A6** | Important | 对接缺口 3（见上） | **给 `build_crud_router` 加 `pk_alias: str | None = None`**：`None` → 自动取**资源路径的单数 + 下划线**（`semesters`→`semester_id`、`course-sections`→`course_section_id`、`fitness-test-results`→`fitness_test_result_id`）。**纯 OpenAPI 层的改名，不动 DB、不动路由匹配。** ⚠️ 23 个 detail 路径的 URL 模板会变，**Task 3 那条遍历型守卫要跟着改** |
| **P4-A7** | Minor | 对接缺口 2（见上） | **原型阶段不修**，但**传导给 Plan 04**：前端不得用 cookie / `credentials:'include'`。已写进「计划边界说明」 |

**计划正文更正**：`_t4_preflight_patch.py`，**6 处替换全部命中 1 次**（硬规矩 #79）。

**⚠️ 一条值得记的正面经验**：本次预检**除了跑探针，还起了真实服务打了一整圈 HTTP** —— 3 个对接缺口里**有 2 个（`securitySchemes` 缺失、`pk_value`）只有从 `/openapi.json` 的实际产物才看得见**，单元测试与 `TestClient` 都不会暴露它们（测试只断言行为、不断言「契约对客户端是否可用」）。**→ 补硬规矩 #104：交付 HTTP 层的 Task，预检必须起一次真实服务、拉一次 `/openapi.json`，并检查三件事：① 每个 2xx 响应有没有 schema；② 客户端必须发的头有没有进 `securitySchemes` 或 `parameters`；③ 路径参数名对生成的客户端是否可读。** 依据：本次查出的 3 个缺口，其中 2 个是「测试全绿但前端接不上」的形状——**而用户的要求逐字是「要确保后端和前端能够对接的上」**。

**下一步**：抽 `task-4-brief.md` → 派实现者。

---

## ✅ Task 4: complete (commits 9062b37..95c7f76, 0 fix round)

**交付**：`482910d`（P4-A1 把 block/课两级投影提成唯一所有者 + 补上 Plan 02 逐字交给 Plan 03 的反向映射与 `regenerate_for_student`；P4-A5 两个身份头注册成 `apiKey` securityScheme + `require_teacher`；P4-A6 给 `build_crud_router` 加 `pk_alias`）、`400d525`（四个特例端点 + schema + 31 条测试）、`95c7f76`（报告）。

**验收（控制者本机亲跑复核）**：
- 全量 **876 → 910 passed**（+34 = `test_prescription_api.py` 31 + `test_crud.py` 3）；带 `--cov` **909 passed, 1 skipped**
- `app/domain/` 四格 **996 / Miss 0 / 288 / BrPart 0 / 100% 逐字未变** ✓
- **扫描面 49 → 50**（api 14 → 15）；**`/api/` 路径模板 47 → 51、操作数 73 → 77**（控制者从 `openapi()` 实读）
- **P4-A5 落地**：`components.securitySchemes` **恰好两格** —— `X-Student-Id` 与 `X-Teacher-Staff-No`，均 `{"type":"apiKey","in":"header","name":<同 key>}`；**挂了 `security` 的操作恰好 4 个**（两个 GET → 学生头、两个 POST → 教师头），**73 个 CRUD 操作一个都没有**（正确：它们不需要身份）。spec 顶层 `security` 为 `None`（也是正确的：不做全局强制）。⚠️ 实现者点明 **`auto_error=False` 是承重的**：缺身份仍返回既有的 **401**，而不是 `APIKeyHeader` 缺省的 403
- **P4-A6 落地**：detail 路径参数名的 distinct 从 **`['pk_value']` 变成 23 个**（`semester_id` / `course_section_id` / `fitness_test_result_id` / …），**`pk_value` 一个不剩**（控制者亲验）
- **P4-A1 落地**：提取出 `_block_payload` 与 `_session_payload`（**课级那三行也提了**，实现者的理由是「留在两处也是两个所有者」），两处调用点 = `training_package_payload` 与新增的 `weekly_sheet_payload`；同形守卫 `test_the_weekly_sheet_blocks_are_field_for_field_the_training_package_ones` **走 HTTP**、两侧是两条真路径（学生侧 `WeeklySheetRead`→`AssembledBlockRead`；教师侧 `PrescriptionRead.training_package: dict`），**故能抓到「`response_model` 静默过滤掉字段」那一类**
- **表数 25**（`prescription` **16 列**）、`_MODELS_PUBLIC_BASELINE` **33**、三个指纹逐字不变、`git diff 9062b37 HEAD -- backend/data` 为空、`pe.db` 不存在 ✓
- **Plan 02 传导的 6 条全部落地**：`paused` 时 `sessions` 原样 / `WeeklySheetRead` 唯一的 float 是 `factor`（**跨单位总量在结构上无处可放**）/ `unspecified` 带 `0.0` / `reason` 空由 domain 判 422 / `old_value`–`new_value` 一律 `str` / 覆盖不继承且 `previous_had_overrides` 在响应里、**`assembly_snapshot` 仍 15 键（一个没加）**

### Ruling 11 — 实现者顶回 3 处，**全部采纳**（Plan 03 的第 15–17 次；累计 **42 次，42 次都对**）

**顶回 1（采纳 → 控制者错误 #15）**：**P4-A6 的自动推导认不出 `-es` 复数。** 派单举的三个例子（`semesters` / `course-sections` / `fitness-test-results`）**都不是 `-es` 结尾**，而 `fitness-test-batches` 会推成 **`fitness_test_batche_id`**。实现者**没有把推导改聪明**，理由是硬的：**`batches` 要去 `es` 而 `exercises` 只去 `s`，两者都以 `ses` 结尾，任何后缀表必然不完备** → 改成让那一行**显式传 `pk_alias`**，顺带给「显式覆盖」那一档一个生产调用方。**控制者亲验 23 个参数名里 `fitness_test_batch_id` 正确、`exercise_id` 也正确**，即两条规则各得其所。

**顶回 2（采纳 → 控制者错误 #14）**：**派单的 Files 清单缺了「JSON → `TrainingPackage` 的反向映射」**，而没有它端点 2/3 **跑不起来**（读出来的 `training_package` 是一个 dict，要还原成 `TrainingPackage` 才能喂给 `weekly_training_sheet` 与 `apply_overrides`）。**Plan 02 结案时逐字写下过「那是 Plan 03 的 API 层的活」，而控制者写 Task 4 的 Files 时没把它捞回来。** 实现者选的住址是 **pipeline 层而非 `app/api/`**，理由成立：**它是 `training_package_payload` 的反面、必须逐格对齐**，且 Task 7/8 也要读同一列。

**顶回 3（采纳）**：**`regenerate` 的实现体放进 `prescription_stage.regenerate_for_student`，并把 16 个列值提进 `_prescription_values` 与批处理共用。** 理由：**在 router 里重抄一遍就是第二个所有者，而 `repo.upsert` 是 PATCH 语义 —— 漏改的那一处会静默沿用旧值**（那是最难查的一类 bug：不报错、只是某个字段永远是旧的）。**回归证据：Plan 02 的 `test_prescription_stage.py` 一条没改、全绿。**

**⚠️ 实现者还自查出一处自己写错的因果陈述**（值得记）：`_replace_previous` 的严格 `<` **今天不可观测** —— 因为 `_prescription_values` 也写 `status`，upsert 会把它写回。它把两处 docstring 改成了如实的「**过度确定**」。**这正是硬规矩 #92/#94 那一族的自查**（不要声称一条守卫能抓到它抓不到的东西）。

**4 处偏离派单字面：全部追认**（① 加了 `deps.require_teacher`——工号在册闸门，与 `require_scope` 第二支同构；② commit 切分与建议不同，理由是 `git add -p` 是交互式的、一个文件只能整体进一个 commit；③ **没实现 `PE_AS_OF` 环境变量**——派单那半句与「测试一律显式传」是替代关系，它做了强的那半，理由是「环境变量是『今天』的第二个所有者，且多一档无消费者的分支」；④ 两处 docstring 的测试名/文件引用写错，进待清扫）。

**变异自证 10/10 RED、0 恒绿**（Ruling 1 说本 Task 不要求变异，实现者自己做了 10 条）。

### ⚠️ Ruling 12 — 那条薄阈值性能测试现在会 flaky，控制者裁定放宽阈值并如实记录

**事实**：`test_backfill_500_students_under_60_seconds` 在**全量跑**时红了两次（`elapsed` = **62.72 s** / **61.58 s**，阈值 60 s）。实现者用 **`git worktree` 在基线 `9062b37` 上对照取证**：单独跑那一条的 setup 时长 **57.21 s（基线）vs 57.39 s（它的）**，差 **0.3%**；基线的全量也跑了 **164.11 s**。**结论：不是本 Task 的回归**——热路径上只多了两次函数调用（≈0.17 s），是**那条薄阈值被机器负载挤过**。清理后重跑 **910 passed** 全绿。

**为什么这件事是承重的**：**一条会 flaky 的测试让「全量绿」这个判据失去意义** —— 后续每个 Task 的验收都要引用它，而它随机红会让实现者与控制者都去追一个不存在的回归（本 Task 的实现者已经为此花了一次 `git worktree` 对照取证）。

**裁定：把阈值从 60 s 放宽到 90 s，并在 docstring 里如实写明三件事**：
1. **spec §1.3 的「500 人整学期回放 < 60 s」在本原型**不予验收**** —— 这与用户 2026-10-08 的裁定一致（「不做性能压测」），Plan 02 已经把 spec §1.3 的那两条改成「未测量」；
2. **保留这条断言的目的是「数量级哨兵」**，不是 60 s 契约 —— Plan 02 Task 7 曾让它真的红到 **115.08 s**（两处全表扫描 + 大 JSON 列 eager 加载），**那才是它要抓的失效形态**；90 s 仍能抓住它；
3. **测量条件**（硬规矩 #42）：Windows / CPython 3.11.1 / SQLAlchemy 2.1.3 / 本地 SQLite 文件 / `elapsed` 只夹 `run_backfill` / **全量跑时的机器负载会把它推过 60 s**（实测 61.58 与 62.72）。
**⚠️ 不选另外两条路**：① 加 `@pytest.mark.perf` 并让默认命令跳过它 —— 那会让「全量绿」这个判据不再覆盖它，而它正是唯一能抓到数量级回归的守卫；② 让它自适应机器负载 —— 那等于取消断言。
**→ 补硬规矩 #105：一条性能断言若在两次以上的全量跑里随机红，就必须当场裁定（放宽并记录测量条件 / 改成相对基线的倍数 / 明确移出默认套件），不许留给下一个 Task 的实现者去撞。** 依据：本次；Plan 01 的 Ruling 228（`--cov` 下余量 0.95× → 加 `gettrace` 跳过钩子）与 Plan 02 Task 7 的 fr1（余量 2.03×）是同一件事的前两幕，**这是第三幕，而这一幕它真的红了**。

### 待清扫：**5 条**，另加一条**能力缺口要传导给 Task 8 / Plan 04**

**⚠️ 能力缺口（实现者报的，控制者裁定归 Task 8）**：**教师端今天没有任何端点能读单个学生的训练单** —— `GET /api/students/{student_id}/weekly-sheet` 挂的是**学生**身份头与 `require_scope`，教师用 `X-Teacher-Staff-No` 调它会 401。**Plan 04 若要「教师点开一个学生看他的本周训练单」（spec §9.1 的大屏与 §9.3 的学生详情都要），Task 8 必须补一个教师身份的变体**（如 `GET /api/teacher/students/{student_id}/weekly-sheet`，用 `require_teacher` + 任教关系校验）。**已按硬规矩 #86 记进 Task 8 的传导清单。**
其余 5 条：两处 docstring 的测试名/文件引用写错；`crud.py` 那张 23 行对照表没有 `pk_alias` 列；`require_scope` docstring 里「教师侧由 Task 8 负责」已过期一半；`_seed` 用 7 键最小快照而 `_profile_of` 若开始读第 8 个键会 `KeyError`。

**下一步**：抽 `task-5-brief.md` → 派实现者（§8.1 三源采集端点）。**⚠️ Task 5 要先做 Ruling 12 那条阈值放宽**（它是「全量绿」判据恢复可信的前提）。

---

### 插曲：用户报 `net::ERR_ABORTED http://127.0.0.1:8000/docs`

**诊断（控制者亲跑）：不是后端的问题。** uvicorn 的访问日志逐字是：
```
GET /docs           HTTP/1.1" 200 OK      ← 六次，全部 200
GET /openapi.json   HTTP/1.1" 200 OK
GET /%40vite/client HTTP/1.1" 404 Not Found   ← 问题在这
```
`/%40vite/client` 解码就是 **`/@vite/client`——Vite 的 HMR 客户端脚本**。**trae-preview 那个面板是为 Vite dev server 设计的**，它会往它加载的任何页面里注入 `<script src="/@vite/client">`；我们的服务是 uvicorn 不是 Vite，这个请求必然 404，于是面板**中止了整个导航**并报 `ERR_ABORTED`。控制者自己用 httpx 打 `/docs` 也是 200。
**处置**：告知用户**在普通浏览器标签页里打开**，不要用预览面板。**Plan 04 的前端是 Vite，那时预览面板就能正常用了** → 已按硬规矩 #86 记进 Plan 04 的约束。
**⚠️ 这条值得记的理由**：`ERR_ABORTED` 看起来像服务端故障，而**证据（访问日志里 `/docs` 是 200、404 的是另一个路径）指向客户端注入**。与 Plan 02 的 P7-A4（`IntegrityError` 看起来像数据坏了，实际是删除顺序）同族：**报错的位置不是原因的位置。**

---

### Task 5: §8.1 三源采集的特例端点 — 预检扫描（Pre-flight，控制者亲跑）

**代码基线**：`fcbb00e`。**测试基线**：`910 passed`；domain **996/0/288/0/100%**；**25 张表**；扫描面 **50**；**51 个端点在线**。
**取证脚本**：`t5_probes/_preflight.py` 与 `t5_probes/_preflight2.py`（两份，因为第一份的输出被管道截断在第 4 节；**⚠️ 这违反 Ruling 1 的「每个 Task 只做一份探针」，但两份是同一份的两个半场、不是两次扫描**）。

#### Ruling 13 — 预检查出 2 Critical / 3 Important / 1 Minor，计划正文更正 4 处

**P5-A1（Critical）：`class_session.batch_id` 与 `training_log.batch_id` 都是 `NOT NULL` 外键指向 `daily_sync_run.id`，而本 Task 要让教师实时建课次、学生实时打卡 —— 这两种行都没有批次可指，照今天的 schema 写进去会当场 `NOT NULL constraint failed`。**
⚠️ **更麻烦的是 `repo.delete_by_batch` 的 docstring 逐字写着「`TrainingLog` 由 Task 5 接（进 `_replay_cleanup`）」** —— 即 **Task 2 是按「`training_log` 是批处理产物」设计的，而 spec §8.1 说它同时是学生每天打卡的落点**。**这张表有两个来源，而 `batch_id NOT NULL` 只容得下一个。**
**裁定：两列都改成 `nullable=True`。** 适配器/批处理写的行带 `batch_id`（`_replay_cleanup` 按批删它们）、**用户实时写的行留 `NULL`** —— 而 `delete_by_batch` 是 `WHERE batch_id = :b`，**SQL 里 `NULL = 任何值` 都不成立 → 实时行天然躲过重放，这正是我们要的**（spec §8.1 的打卡是学生的作业，重放不该删掉它）。
⚠️ **`_BATCH_OWNED_TABLES` 那条守卫不受影响**（它断言的是「**有 `batch_id` 列**的表恰好是那九张」，可空性不改变列的存在）。⚠️ 但 `repo.delete_by_batch` 的 docstring 要同步（硬规矩 #66）。
**→ 控制者错误 #16**：Task 2 的字段清单里，`batch_id` 的「带 / 不带」是按**「这张表是不是批处理产物」**二分决定的（四张带、三张不带），而**真实情况是「这张表的行有没有批次来源」——`training_log` 两个来源都有，二分法容不下它**。**这与 Plan 02 的控制者错误 #5（把「枚举分桶的 6 个结果」当成「分层判定的 3 个结果」）同型：用一个二分/三分类去套一个实际上有更多档的东西。**
**→ 补硬规矩 #106：给一张表定「带不带某个归属列」时，先列出这张表的全部写入来源；只要有两个以上的来源、而其中至少一个没有那个归属，那一列就必须可空。** 依据：P5-A1 / 控制者错误 #16。

**P5-A2（Critical）：`TrainingPackage` 没有 `weekly_frequency` 字段** —— 实测字段只有 `template_id` / `template_version` / `weeks` / `assembly_snapshot` / `paused`。而计划把完成率的分母定成「= `Template.weekly_frequency`」，**从处方行里读不到它**。
**裁定：分母改成 `len(sheet.sessions)`。** ⚠️ **这个改法不只是「能读到」，它比原方案更对**：`Template.weekly_frequency` 是模板的静态值，而**教师用 `OverrideKind.WEEKLY_FREQUENCY` 覆盖过之后，`weekly_training_sheet` 产出的 `sessions` 已经反映了覆盖后的天数** —— 用 `len(sheet.sessions)` 当分母，**教师改了周天数，完成率的分母会跟着变**，而读模板值不会。**无处方、或 `current_week` 返回 `None`（处方已到期）→ 完成率返回 `null` 而不是 `0`。**
**→ 控制者错误 #17**：写「分母 = `Template.weekly_frequency`」时**没有核实它在 API 层能不能读到** —— 它是 domain 的 `Template` 的字段，而端点手上只有 `Prescription` 行与它的 `training_package` JSON。**这与 Plan 02 的控制者错误 #148 同型**（「只核了 `LastPrescription.microcycle_weeks` 有没有住址，没把 5 个字段逐个对到列上」）—— **都是「在一个层里引用另一个层的字段，没核那一层手上有没有它」**。

**P5-A3（Important）：`training_log.source` 是 `VARCHAR(16) NOT NULL`，但 `TrainingLog` 没有 `SOURCES` 类常量、也没有对应的 CHECK**（实测该表只有 `ck_training_log_feeling` 一条）。而 P5-A1 说明这张表有两个来源 —— **值域没有单一所有者**。裁定：加 `TrainingLog.SOURCES`（至少 `{"checkin", "lepao"}`，**学生打卡的端点写 `"checkin"`**）+ 按 `feeling` 的既有做法用 `_in_domain` 加一条 CHECK。⚠️ **加 CHECK 是 schema 变更 → `test_models.py` 里「`_in_domain` 列数 = 23」那条断言会红**（硬规矩 #88）。

**P5-A4（Important）：`app/config.py` 今天没有 `TIMEZONE`**（实测只有 `BACKEND_DIR` / `DEFAULT_CSV_DIR` / `DEFAULT_DB_URL`）。**`zoneinfo` 可用** ✅（实测 `ZoneInfo("Asia/Shanghai")` 与 `datetime.now(z)` 都正常，**无 tzdata 缺失问题**）。本 Task 新增 `TIMEZONE = "Asia/Shanghai"`。⚠️ **`DEFAULT_DB_URL` 实测逐字是 `sqlite:///…/backend/pe.db`（禁区）**。

**P5-A5（Important）：`deps.Page` 实测是一个 FastAPI 依赖函数、不是 Pydantic 模型** —— `def Page(*, limit: Annotated[int, Ge(ge=1), Le(le=200)] = 50, offset: Annotated[int, Ge(ge=0)] = 0) -> None`。**计划 Task 1 的 Interfaces 写的 `Page(BaseModel)` 是错的**（Task 1 的实现者选了依赖函数，因为查询参数用 `Annotated` 更自然）。**本 Task 照实测的形状用 `page: Page = Depends()`，不要去改 `Page`**（Task 3 的 23 个资源都在用它）。**→ 控制者错误 #18：计划的 Interfaces 一节写了一个与实现不符的类型**，而 Task 3 的实现者照实测的形状用了、没有顶回来（因为它没有理由去核 Task 1 的 Interfaces 那一句）——**这正是「Interfaces 一节是后续 Task 的唯一契约来源」这句话的代价：它一旦写错，后面每个 Task 都要靠自己实测才能发现。**

**P5-A6（Minor）：`ClassSession` 没有任何类常量**，而 `rpe_token` 是 `VARCHAR(16)`、本 Task 要用 `secrets.token_urlsafe(12)[:16]` → **`16` 会成为两个没有出处的魔数**。裁定：加 `ClassSession.RPE_TOKEN_LEN = 16`，列类型与生成代码都引它。
**⚠️ 顺带核实到架构守卫不拦 `secrets`**：实测 `_is_api_allowed` 是**只针对 `app.*` 前缀**的 allow-list（`FORBIDDEN_PREFIX = "app.seed"`），**标准库不受它约束**。

**⚠️ 两件核实到的好事**（不用改，但值得记，因为它们说明前序 Task 的实现者做得比派单要求的更远）：
1. **Task 1 的守卫 allow-list 已经预留给 Task 6 与 Task 9**：`_API_ALLOWED_PREFIXES` 里有 `app.refdata_alerts`（**今天还不存在**，Task 6 才建）与 `app.adapters`（Task 9 的 `POST /api/pipeline/run-daily` 要它，因为 `daily.run_daily` 的第四个参数是适配器实例、而 `build_adapter` 住在 `app.adapters.factory`）。docstring 逐字写着「allow-list 里列一个尚不存在的模块是安全的（它是许可、不是断言），而列在这里正是为了兑现『后面 8 个 Task 不再动本文件』」。**S6 那条裁定被完整兑现了。**
2. **`repo.delete_by_batch` 的 docstring 已经把 Task 5/8 的活写清楚了**：「`Alert` 与 `WeeklyClassReport` 由 Task 8 接进清单，`TrainingLog` 由 Task 5 接，而 **`ClassSession` 不得接**——`rpe_record.class_session_id` 是 NOT NULL 的外键指向它，按批删课次会当场 FK 违例（改成 `CASCADE` 更糟：会连带删掉学生刚交的快评），它的幂等手段是 `upsert` 按 `(course_section_id, session_date, period)` 更新」。**本 Task 照它办。**

**计划正文更正**：`_t5_preflight_patch.py`，**4 处替换全部命中 1 次**（硬规矩 #79）。

**下一步**：抽 `task-5-brief.md` → 派实现者。**⚠️ 本 Task 的第一件事是落地 Ruling 12 那条阈值放宽**（`assert elapsed < 60` → `< 90` + docstring 如实改写），因为「全量绿」这个判据要先恢复可信。

---

## ✅ Task 5: complete (commits acd3f53..c61dc3c, 0 fix round)

**交付**：`d933bac`（**Ruling 12 第一件事**：`elapsed < 60` → `< 90`、函数名 → `under_90_seconds`、docstring 按「数量级哨兵」重写；连带同步 `app/pipeline/backfill.py` 与 `daily.py` 里两处旧函数名/旧阈值，**全仓 AST 复核旧名命中 0**）、`c8f77cc`（P5-A1/A3/A4/A6 的 schema 变更 + **`training_log.submitted_at` 新列** + 全部连带，含三个读/写模型的 `batch_id` 改可空、`demo_data` 填新列）、`3be0bc1`（七个端点 + 46 条测试 + 13 个特例 schema + **include 顺序变承重**）、`c61dc3c`（报告）。

**验收（控制者本机亲跑复核）**：
- 全量 **910 → 956 passed**（+46，**零退步**）；带 `--cov` **955 passed, 1 skipped**（那 1 条 skip 就是 Ruling 12 的哨兵，带 cov 时按 `sys.gettrace()` 跳过）
- `app/domain/` 四格 **996 / Miss 0 / 288 / BrPart 0 / 100% 逐字未变** ✓
- **扫描面 50 → 51**（api 15 → 16）；**`/api/` 路径模板 51 → 56、操作数 77 → 84**（控制者从 `openapi()` 实读）；**表数仍 25**；`_MODELS_PUBLIC_BASELINE` **仍 33**
- **七个端点逐个亲验在线**：`POST /api/class-sessions/{class_session_id}/open-rpe`、`POST /api/rpe-records`、`GET /api/class-sessions/{class_session_id}/rpe-status`、`POST /api/training-logs`、`GET /api/students/{student_id}/training-logs/completion-rate`、`POST /api/mini-tests/batch`、`GET /api/mini-tests/normalized`；**挂了 `security` 的操作数从 4 扩到 11**
- **P5-A1 落地亲验**：`class_session.batch_id` 与 `training_log.batch_id` 实测 **`nullable=True`**，**且 `ClassSessionRead` / `TrainingLogRead` / `ClassSessionCreate` 三个 Pydantic 模型的 `batch_id` 都跟着改成 `int | None`**（顶回 3 的连带）；其余七张带 `batch_id` 的表仍 `False`、FK 与索引都未动
- **顶回 4 落地亲验**：`training_log` **11 列**（原 10）、`submitted_at` 存在且 `nullable=False`；`TrainingLog.SOURCES = {'checkin','demo','lepao'}`；新 CHECK **`ck_training_log_source`**；`ClassSession.RPE_TOKEN_LEN = 16`
- **顶回 5 落地亲验**：`routers/__init__.py` 里 **`feedback` 的 include 位置在 `catalog` 之前**，且**「顺序今天不承重」那句已消失**
- **Ruling 12 落地亲验**：`test_backfill.py` 里 **`under_90_seconds` 在、`under_60_seconds` 不在**；**`elapsed < 90` 在、`elapsed < 60` 不在**
- `config.TIMEZONE = 'Asia/Shanghai'`（**P5-A4 落地**）
- **禁区**：三个指纹逐字不变、`git diff acd3f53 HEAD -- backend/data` 为空、`pe.db` 不存在、`data/seed/` 0 文件
- **⚠️ 控制者已按实现者的提醒删掉陈旧的 `pe_demo.db`**（`training_log` 新增了 `submitted_at NOT NULL`，而 `init_db` 走 `create_all`、**对已存在的表原样跳过** → 旧库里没有这一列 → `POST /api/training-logs` 会 500）。实现者全程**没有碰** `pe_demo.db`（真机冒烟一律用 TEMP 库、端口 8123，28/28 全绿，结束时已 terminate 并删除）

### Ruling 14 — 实现者顶回 8 处，**全部采纳**（Plan 03 的第 18–25 次；累计 **50 次，50 次都对**）

**⚠️ 其中 5 条是控制者错误，逐条记在下面。这是 Plan 03 单轮最多的一次，且三条是 Critical。**

**顶回 3（Critical，采纳 → 控制者错误 #19）**：**P5-A1 的连带不全。** 控制者的更正只说了「两列改成 `nullable=True`」，而**没有说 Pydantic 的读写模型也要跟着改**：`ClassSessionRead.batch_id: int` 与 `TrainingLogRead.batch_id: int` 不改，**第一条 `NULL` 行就会让端点 500**（把「用户实时写的行」伪装成服务器故障）；`ClassSessionCreate.batch_id` 不改，**「教师实时建课次」仍然做不到**。
**⚠️ 这与 Plan 03 的 P3-A1 是同一形状**（那次是「`models/__init__.py` 对 `ops.py` 是星号导入」的连带没写进更正），也与 Plan 02 的控制者错误 #151 同族（**指出了问题而没给出完整路径**）。
**→ 硬规矩 #98 再扩写：派单里写「把 X 改成 Y」时，必须同时列出 X 的**全部**镜像位置（DB 列 / Pydantic 读写模型 / 生成器 / 测试的形状断言 / docstring），而不只是最先想到的那一个。** 依据：#19。

**顶回 4（Critical，采纳 → 控制者错误 #20）**：**`training_log` 没有 `submitted_at` 列，而控制者自己的决定 ② 逐字用它作判据**（「`late` 只看 `submitted_at` 的时刻，`log_date` 是学生在补哪一天」）。**这是「计划引用了一个不存在的东西」这一族的第 N 次**——而 Plan 02 的 9 个 Task，预检**每一轮**都查出 2–4 条这一族的问题，控制者在 Plan 03 的 Ruling 1 里逐字把这句话当成「保留预检」的理由，**然后自己在同一个 Task 里写了一条引用不存在列的决定**。
实现者的处置：**加列**（`submitted_at DATETIME NOT NULL`），并明确不选替代方案（「把补卡编码进 `late`」会**不可逆地混掉两档**：迟到与补卡是两件不同的事）。连带动了不在清单里的 `demo_data.py` 与 `test_crud.py`。
**→ 这一条不需要新硬规矩**（#91 与 #97 已经覆盖），**但需要记账：控制者在写「决定」时引用字段名的那一刻，没有回到字段清单核对。**

**顶回 5（Critical，采纳 → 控制者错误 #21）**：**路由冲突。** `GET /api/mini-tests/normalized` 与泛型 CRUD 的 `GET /api/mini-tests/{mini_test_id}` **完全同形**，而 `routers/__init__.py` 当时**逐字写着「顺序今天不承重」**。照它做会得到 **422 +「`mini_test_id` 不是一个整数」**，而那个报错会把下一个人支去修前端（他会以为是前端传错了参数）。
实现者的处置：**特例 include 在 `catalog` 之前** + 加一条守卫 + **M6 反证**（把顺序换回去，守卫变红）；那两段 docstring 按实际改写。
**⚠️ 它同时指出一条必须传导的口径**：**读取侧的重叠没有 `writable=False` 那样的开关可用，只能靠 include 顺序** —— 因为 `GET` 是 23 个资源全都有的，而特例端点的子路径（`/normalized`、`/rpe-status`、`/completion-rate`）在 FastAPI 的路由匹配里与 `/{pk}` 同形。**→ 已按硬规矩 #86 记进 Task 7/8/9 的传导清单。**

**顶回 1（采纳 → 控制者错误 #22）**：**P5-A5 是事实错误** —— `deps.Page` 现场是 **`class Page(BaseModel)`**（`deps.py`），**不是**控制者说的「FastAPI 依赖函数」。
**⚠️ 根因是控制者探针的工具选错了**：探针用 `callable(o) and o.__module__ == deps.__name__` 来挑「公开函数」，**而 Pydantic 的 BaseModel 子类也是 callable 的**，于是 `inspect.signature(Page)` 打出的是它 `__init__` 的签名 `(*, limit: Annotated[...] = 50, offset: ... = 0) -> None`，**看起来完全像一个依赖函数**。
**这与控制者错误 #12（用文本计数去核一张数据驱动的表）是同一族：探针的工具选错，产出一个看起来合理的错结论。** 而 #12 立的硬规矩 #103 说的是「一个探针里若有两种口径，以运行时那一种为准」—— **本次的教训更基础：运行时口径本身也可能是错的，如果挑取对象的谓词写错了。**
**→ 补硬规矩 #107：探针里用谓词挑对象时（`callable` / `inspect.isclass` / `isinstance`），必须先对**一个已知反例**验证谓词真的把它排除掉；`callable()` 会把类、 functools.partial 与带 `__call__` 的实例全都放进来。** 依据：#22；与 #103 配套（#103 管「选哪个口径」，#107 管「口径本身对不对」）。
**⚠️ 顶回的结论不受影响**（`Page` 的形状是什么，本 Task 七个端点一个都没用到它），**但计划正文里那句 `Page(BaseModel)` 的「更正」本身是错的，要在 Task 9 的勘误里改回来**（原计划 Task 1 的 Interfaces 写的 `Page(BaseModel)` **是对的**，控制者的 P5-A5「更正」把它改错了）。

**顶回 2（采纳）**：**P5-A3 说的「`test_models.py` 里『`_in_domain` 列数 = 23』那条断言会红」不成立** —— 实测那是一条**下界** `assert len(domains) >= 10`（注释逐字写「刻意不逐 Task 抬高」），「23」只是 docstring 里的散文。**故加 CHECK 不会让任何断言红。** 跑全量后真正红的是 **2 条**（`test_the_seven_plan03_tables_have_the_documented_shape` 的形状元组、`test_the_identity_headers_are_registered_as_openapi_security_schemes` 的 `expected` 从 4 项扩到 11 项）。**⚠️ 控制者又是照着「上一个 Task 的红点清单」推理，没有实测这一个 Task 会红哪些**（与 Plan 02 的控制者错误 #144 同族：抄上一个 Task 的数）。

**顶回 6（采纳，且它的处置是本轮最值得学的一处）**：**Ruling 12 的证据在它本机未复现** —— 全量 `pytest -q` n=2 实测 **47.33 s / 47.96 s**（对 60 的余量 **1.25×**），即**它没真的红过、只是余量薄**。它的处置：**把 docstring 里 flaky 的依据从「越界」换成「余量 < 2×」，没有把控制者报的 61.58/62.72 写成自己亲跑的值**。并给出一个数据点：**本机满足 2× 线的阈值是 96 s 且仍抓得住 Plan 02 那次真实的 115.08 s，即本机 96 严格优于 90**；仍按裁定落 90，并说「要抬到 96 请连同你那台机器复测」。
**⚠️ 控制者裁定**：**保持 90**，理由：① 90 是两台机器都能过的值（控制者那台实测 61.58/62.72，实现者那台 47.33/47.96），96 只在一台机器上有 2× 余量；② 90 仍能抓住 115.08 s 那次真实回归（余量 1.28×，够响）；③ **docstring 里两个数都记**（控制者的 61.58/62.72 与实现者的 47.33/47.96），并注明「两台机器差 1.3×，故阈值取两者都能过且仍抓得住 115 的那个」。**⚠️ 这条裁定要传导给 Task 9 的勘误。**

**顶回 7（采纳 → 控制者错误 #23）**：**P5-A2 的例子方向错了。** 控制者说「教师用 `OverrideKind.WEEKLY_FREQUENCY` 覆盖过之后，`sessions` 已经反映了覆盖后的天数」，并举例要用「覆盖成 4」验证分母跟着变。而 **`WEEKLY_FREQUENCY` 覆盖的效果逐字是「保留前 N 课」→ 只能减不能加**（Plan 02 Task 6 的 F6-4 与 `test_a_larger_weekly_frequency_override_clamps_to_the_available_sessions`）。**故控制者那条守卫会绿着但什么都没验**：红层模板本来就是 4 课，覆盖成 4 仍是 4，与「读模板值」同数 —— **两侧同源于失效**。
实现者改成：**红层 4 天 → 覆盖成 2 天 → 分母应为 2**。**⚠️ 这是硬规矩 #92 的第 6 次同型**（要求一条测试覆盖一个结构上不可达/无效的场景）。

**顶回 8（采纳）**：**分母的口径偏离** —— 实现成「**处方训练日 ∩ 所查学期周**」而非字面的 `len(sheet.sessions)`。**理由成立**：同样兑现裁定的理由（反映教师覆盖），且**处理了错位**（`generated_on` ≠ 学期第一天在真实数据里是常态，字面用 `len(sheet.sessions)` 会在错位时取到错误的周）。**对齐时两者逐字相同，各有一条守卫。**

### 7 处偏离派单字面：全部追认

加 `submitted_at` 列 / 动 `demo_data.py` / 动 `test_crud.py` / 动 `test_prescription_api.py` / 分母取交集 / **`prescription` router 一并前移**（让规则统一成「特例一律在泛型之前」，行为无变化）/ 七个端点都没用 `Page`。**「不做」的三件（扫码签到、口令过期、真实鉴权）一件都没做** ✓

### ⚠️ 实现者报的两条对后续 Task 有用的口径发现（控制者亲验并采纳）

1. **FastAPI 0.141.1 / Starlette 1.7.0 上 `include_router` 不再把子路由展平进 `app.routes`**（实测 `len(app.routes) == 6`，全部 include 的路由折叠成**一个** `_IncludedRouter`）→ **「遍历 `app.routes` 数端点」这个口径在本版本不完整，一律改用 `openapi()["paths"]`**。（Task 3 的实现者也报过同一条，两次独立发现 → 这条要写进计划的 Global Constraints，Task 9 的勘误里落。）
2. **⚠️ 架构守卫会 AST 解析工作树里的全部 `.py`，含未入库的 `t5_probes/`** —— 实现者第一版探针有一句 f-string 含反斜杠，**当场让 `test_absolute_folding_matches_resolve_name` 红 2 条**。**控制者的 `_preflight.py` / `_preflight2.py` 同样在扫描范围内。**
   **→ 补硬规矩 #108：探针脚本不得含反斜杠的 f-string、不得含语法错误、不得在模块级 import 生产模块以外的东西 —— 因为架构守卫会 AST 解析工作树里的**全部** `.py`（含未入库的探针目录），一个探针的语法问题会让守卫红在一个看不出所以然的地方。写探针前先 `python -m py_compile` 一次。** 依据：本次；与控制者错误 #12/#22 同族（探针本身是错误来源）。

### 待清扫：**4 条**（无 Critical）

`schemas/feedback.py` 资源表里指向已完成 Task 序号的措辞；`models/feedback.py` 顶部表里 `alert`/`notification`/`weekly_class_report` 三行仍是**未完成的预告**（**留给 Task 7/8/9 各自结案时改，谁兑现谁改写**）；**单人班百分位给 50.0 看起来像真排过名**（**建议 Plan 04 在 `scored_count == 1` 时显示「无排名」** → 已按硬规矩 #86 记进 Plan 04 的约束）；4 个工程决定要登记 spec §14（归 Task 9）。

### ⚠️ 按硬规矩 #86 回扫 Task 6/7/8/9 与 Plan 04

1. **Task 7/8/9**：**特例路由必须 include 在 `catalog` 之前**（顶回 5）—— 读取侧的重叠没有 `writable=False` 那样的开关可用，只能靠顺序。Task 7 的 `POST /api/alerts/{id}/handle`、Task 8 的 `GET /api/dashboard/...` 与 `POST /api/notifications/{id}/read`、Task 9 的 `POST /api/pipeline/run-daily` **都要照这条办**，且**每个都要有一条守卫钉住顺序**（Task 5 已建了一条可复用的形状）。
2. **Task 8**：`_replay_cleanup` 接 `TrainingLog` 时注意 **`batch_id` 现在可空**（实时打卡的行是 `NULL`，`WHERE batch_id = :b` 天然删不到它们，**这正是我们要的**，但 docstring 要写明）。
3. **Task 9**：① `demo.ps1` 的第一步必须**删掉旧的 `pe_demo.db`**（本 Task 已经撞上一次：`create_all` 对已存在的表原样跳过，新增的 NOT NULL 列不会补上）；② **勘误里要把 P5-A5 那句「`Page` 是依赖函数」改回 `Page(BaseModel)`**（控制者的「更正」本身是错的）；③ 把「`openapi()["paths"]` 才是端点计数的口径」写进 Global Constraints；④ Ruling 12 的阈值裁定按顶回 6 的口径记两个数。
4. **Plan 04**：① 不得用 cookie / `credentials:'include'`（P4-A7）；② **单人班百分位显示「无排名」**（本 Task 的待清扫第 3 条）；③ 预览面板会往页面注入 `/@vite/client`，**Vite 项目下这是正常的**。

**下一步**：抽 `task-6-brief.md` → 派实现者（`alert_rules.yaml` + `app/domain/alerts.py`，**本计划唯一要求变异测试的 Task**）。

---

### ⚠️ 控制者亲验的两处「不符项」经复核**全部是探针工具选错**，实现者的报告是对的（控制者错误 #24）

控制者的 `_t5_close.py` 里那节亲验跑出两条 ⚠️：① 「`feedback` 的 include 位置在 `catalog` **之后**」；② 「`routers/__init__.py` 里仍写着『顺序今天不承重』」。**两条都是假的**，用 `t5_probes/_recheck.py` 复核坐实：

**① include 顺序**：实测 `routers/__init__.py` 的三行 `include_router` 是
```
:74 api_router.include_router(feedback_router)
:75 api_router.include_router(prescription_router)
:76 api_router.include_router(catalog_router)
```
**特例确实在泛型之前 ✅**（顶回 5 完整落地）。控制者的探针写的是 `ri.find("feedback") < ri.find("catalog")` —— 而 **`find()` 找的是子串首次出现**，命中的是 **:48/:49 的 import 行**（`from app.api.routers.catalog import …` 按**字母序**排在 `feedback` 之前），不是 include 行。**探针量的是 import 顺序，报出来的是 include 顺序。**

**② 「顺序今天不承重」**：实测该文件的 docstring **已经按实际改写**，逐字是「⚠️ **include 的顺序是承重的**（计划 S4 那段裁定的由来）」，并**分写入侧与读取侧两半讲清了对策**（写入侧靠 `writable=False` 让重叠不存在；**读取侧靠顺序，因为重叠消不掉**——「读端点是泛型工厂的核心产出，关掉它等于关掉整个资源的 read」），还逐字写了「**Task 4 的四个路径与顺序无关**（本处此前写的是「include 的顺序今天不承重」，那句话在 Task 5 之后已经不成立，按实际改写）」。控制者的探针 `'顺序今天不承重' in ri` **匹配到的正是那句更正说明里对旧文本的引用** —— **把「记录旧文本」当成了「旧文本仍在」**。

**⚠️ 这两条的性质**：**控制者在写下硬规矩 #107（「探针里用谓词挑对象时，必须先对一个已知反例验证谓词真的把它排除掉」）之后不到十分钟，就在自己的亲验探针里犯了同一族的错两次**，而且两次的形状还不一样（一次是**挑错了对象**：`find()` 挑到 import 行；一次是**谓词匹配到了对旧文本的引用**）。
**→ 控制者错误 #24。** 若没有复核这一步，这两条会被写进账本成为「实现者没按顶回 5 办」的假发现，并可能引发一轮完全无谓的 fix round。
**→ 补硬规矩 #109：亲验探针跑出「不符项」时，必须先用第二个独立工具复核那一条，才允许把它写进账本或派成 fix round。** 依据：#24（两处不符全是探针错）；Plan 02 的控制者错误 #67 是同一形状（把复审者「三种形状全部假绿」的归纳照抄进账本，实测其中一格本来是对的），**这是第 2 次**。
**⚠️ 与 #107 的关系**：#107 管「写探针时先验证谓词」，#109 管「探针报红时先复核再采信」。**两条都是必需的**——#107 是事前，而本次证明事前那条**刚写完就会被违反**，故事后的 #109 才是真正的兜底。

**其余各节全部亲验通过**（`_t5_close.py` 的输出）：`956 passed`；覆盖率四格 **996/0/288/0/100% 逐字未变**；扫描面 **50 → 51**；**`/api/` 路径模板 56、操作数 84**；七个端点逐个在线且方法正确；**挂 `security` 的操作数 4 → 11**；`class_session.batch_id` 与 `training_log.batch_id` 实测 `nullable=True` **且三个 Pydantic 模型（`ClassSessionRead` / `TrainingLogRead` / `ClassSessionCreate`）的 `batch_id` 都是 `int | None`**（顶回 3 的连带完整）；`training_log` **11 列**、`submitted_at DATETIME NOT NULL` 已加（顶回 4）；`TrainingLog.SOURCES = {'checkin','demo','lepao'}` + `ck_training_log_source` 已加（P5-A3）；`ClassSession.RPE_TOKEN_LEN = 16`（P5-A6）；`config.TIMEZONE = 'Asia/Shanghai'`（P5-A4）；表数 **25**、`_MODELS_PUBLIC_BASELINE` **33**；`elapsed < 60` 已绝迹、`elapsed < 90` 在（Ruling 12）；`deps.Page` 实测**是 `class Page(BaseModel)`**、`model_fields = ['limit','offset']`（坐实顶回 1 与硬规矩 #107 的出处）；**陈旧的 `pe_demo.db` 已删（249 856 B）**；三个指纹逐字不变、`git diff acd3f53 HEAD -- backend/data` 为空、`pe.db` 不存在。
⚠️ **`under_60_seconds` 在 `test_backfill.py` 里仍有文本命中**，而实现者报「全仓 AST 复核旧名命中 0」—— 按 #109，**这一条在控制者用 AST 独立复核之前不采信为发现**（最可能与 ② 同型：docstring 里记录旧名）。**归 Task 9 的勘误一并核**，不阻塞结案。

**Task 5 结案口径**：**0 fix round**（两条「不符项」经查是控制者的探针错，不构成发现）。

---

### Task 6: 预警规则（`alert_rules.yaml` + `app/domain/alerts.py`）— 预检扫描（Pre-flight，控制者亲跑）

**代码基线**：`4e7cc08`。**测试基线**：`956 passed`；domain **996/0/288/0/100%**；**25 张表**；扫描面 **51**；**56 个端点在线**。
**取证脚本**：`t6_probes/_preflight.py`（一份，Ruling 1 的口径）。⚠️ **按硬规矩 #108 先 `python -m py_compile` 过一遍再跑**（架构守卫会 AST 解析工作树里的全部 `.py`，含未入库的探针；Task 5 的实现者就撞过一次：探针里一句含反斜杠的 f-string 让 `test_absolute_folding_matches_resolve_name` 红 2 条）。

#### Ruling 15 — 预检查出 1 Critical / 1 Important / 2 确认 / 1 Minor，计划正文更正 4 处

**P6-A1（Critical）：`StudentSignals` 带不出 `window_key`。** 计划的字段清单是 `rpe_streak: int` / `mini_test_scores: tuple[float, ...]` / `checkin_gap_days: int` / `completion_rate: float | None` / `mini_test_improved: bool` —— **一个 id 都没有**。而 `StudentHit.window_key` 的算式逐字要「`f"rpe{第 3 次快评的 class_session_id}"`」与「`f"mt{mini_test_scores 最后一项的 id}"`」。**`ClassSignals` 同样缺**：它只有 `mean_rpe` / `student_count`，而 `YELLOW_CLASS_RPE_HIGH` 与 `GREEN_MASTERY` 的 `window_key` 是 `f"{semester_id}:{week}"`。
**裁定**：`StudentSignals` 加 `rpe_session_ids: tuple[int, ...]`（与 `rpe_streak` 平行）与 `mini_test_ids: tuple[int, ...]`（与 `mini_test_scores` **同序**）；`ClassSignals` 加 `semester_id: int` 与 `week: int`。
**⚠️ 为什么把 id 放进 domain、而不是让 Task 7 在 I/O 层拼 `window_key`**：`window_key` 是**去重键**，它承重的是 Review Focus 第 3 条（「同一次触发只有一条 alert、只推一次减量 20%」，否则 `0.8³ = 0.512`）—— **放在 domain 里它是纯函数、能被单元测试穷举；放在 `alert_stage` 里它只能靠集成测试撞**。这与 Plan 02 的 Ruling 96（「值类型住 domain、加载器住 domain 外」）是同一条纪律。
**→ 控制者错误 #25**：**写「输出结构体有一个字段 X」时，没有回头核「输入结构体带得出 X 吗」**。这与 Plan 03 的控制者错误 #17（`TrainingPackage` 没有 `weekly_frequency`）、Plan 02 的 #148（`LastPrescription` 的 5 个字段没逐个对到列上）是**同一族的第 3 次** —— 都是「在一个结构里引用另一个结构的字段，没核对方手上有没有它」。
**→ 补硬规矩 #110：定义一个纯函数的输出结构时，逐字段回问「这个值从哪个入参来」；答不上来就是入参缺字段，而不是「实现时再想办法」。** 依据：#25 / #17 / #148。**⚠️ 这一族已经三次了，而三次都是预检或实现者抓到的、没有一次是控制者写的时候自己抓到的。**

**P6-A2（Important）：YAML 报错的那套助手是 `refdata_prescription.py` 的私有函数，「照抄」等于复制、复制就是第二个所有者。** 实测它有 **16 个私有函数**，其中**通用的 6 个**是 `_line_index(text) -> dict[tuple,int]`、`_fail(path, lines, key_path, message) -> ValueError`、`_exact_keys(path, lines, where, raw, required, label) -> None`、`_as_float(...)`、`_as_int(...)`、`_as_optional_text(...)`。
**裁定：抽公共模块 `app/refdata_yaml.py`**，把那 6 个搬进去（**改名去掉前导下划线**，因为它们跨模块了），`refdata_prescription.py` 与 `refdata_alerts.py` 都从它 import。⚠️ **这与 Plan 02 遗留的那条 Minor 是同一条纪律**（「两份守卫的重复代码在 Plan 03 加第三个守卫时必须抽公共模块」）—— 那次说的是架构守卫，这次说的是 YAML 加载器，**形状一样**。
⚠️ **搬的是私有助手、不改 `refdata_prescription.py` 的公开面** → `_PRESCRIPTION_PUBLIC_BASELINE`（**24 个二元组**）**不动**；**指纹测试钉的是 YAML 文件、不是 `.py`** → 也不动。⚠️ `app/refdata_yaml.py` 在 `app/` 根下，**不在 `SCANNED_DIRS` 任何一项里**（与 `app/main.py` / `app/config.py` / `app/refdata.py` 同档），故架构守卫不扫它、**扫描面也不因它而涨**（只涨 `app/domain/alerts.py` 那一个：51 → 52）。

**P6-A3（确认，无需改）：两份守卫的下界全是 `>=`** —— `test_domain_purity.py` 的 `len(scanned) >= 5`、`len(real_py) >= 40`、`relative_seen >= 16`；`test_layering.py` 的 `len(scanned) >= 18`（= pipeline 5 + db 5 + domain 5 + api 3）、`len(api_py) >= 3`、`len(reverse_py) >= 15`、`len(cases) >= 22`。**加一个 domain 模块（16 → 17，扫描面 51 → 52）不会让任何一条红。S6 的裁定兑现了：本 Task 不需要动任何下界断言。**

**P6-A4（确认，无需改）：`ALLOWED_MODULES` 实测 = `{collections, collections.abc, dataclasses, enum, numpy, typing}`** —— `alerts.py` 要的 `dataclasses` / `enum` / `collections.abc` / `typing` **全在里面**，**不需要改 purity 守卫**。⚠️ 但 **`datetime` 不在白名单** → `alerts.py` 不得 import 它。**若日期字段的类型注解绕不过去（写 `dt.date` 就要 import），实现者应顶回来**，可选的处置有三：注解写成字符串形式（`"dt.date"` 仍需 import 才能求值，故不行）、干脆不注解那两个字段、或**把日期字段换成调用方已算好的 `str`**（控制者倾向第三个：`window_key` 里要的本来就是 ISO 串）。

**P6-A5（Minor）：`refdata_prescription.py` 没有 `__all__`** —— 它的公开面是靠 `test_refdata_prescription.py` 的 `_PRESCRIPTION_PUBLIC_BASELINE`（**24 个 `(名字, 所有者模块)` 二元组** + `assert len(...) == 24`）从**外部**钉住的。**裁定：`refdata_alerts.py` 照它的形状办（不写 `__all__`）**，改在 `tests/test_refdata_alerts.py` 里建 `_ALERTS_PUBLIC_BASELINE` + `assert len(...) == <自己数>`（**数用运行时口径**，硬规矩 #89）。⚠️ 而 **`app/domain/alerts.py` 要写 `__all__`**（它是 domain 模块，与 `app/domain/prescription/*.py` 同档，那些都写）。

**顺带核实到的**：`app/domain/` 今天 16 个 `.py` = 顶层 6 个（`__init__.py` 0 B、`derive.py` 39 717 B、`indicators.py` 23 244 B、`percentile.py` 43 088 B、`stratify.py` 18 851 B、`tables.py` 1 495 B）+ `prescription/` 子包 10 个。**`alerts.py` 放顶层是对的**（它与 `prescription/` 无隶属关系；而 spec §8.2 的预警规则也不属于处方装配）。`Alert` 表的类常量实测有 `LEVELS` / `STATUSES`（`level` ∈ red/yellow/green、`status` ∈ pending/handled/ignored），**`AlertLevel` 枚举的值要与 `Alert.LEVELS` 逐字一致**（单一所有者的问题：谁拥有那三个字符串？裁定 **`app/domain/alerts.py` 的 `AlertLevel` 是所有者，`Alert.LEVELS` 是它的 DB 镜像** —— 但 `Alert.LEVELS` 今天已经存在且被 `_in_domain` 用着，故本 Task **不改它**，改为**加一条测试断言两者逐字相等**）。

**计划正文更正**：`_t6_preflight_patch.py`，**4 处替换全部命中 1 次**（硬规矩 #79）。

**下一步**：抽 `task-6-brief.md` → 派实现者。**⚠️ 本 Task 是本计划唯一要求变异测试的**（Ruling 1：5 条规则的比较符各做一次，断言对应的边界测试变红；按硬规矩 #83 的 `.pyc` 纪律做，且**每条变异要先论证它在结构上可达**——硬规矩 #92）。

---

## ✅ Task 6: complete (commits a8d61b4..caf80c5, 0 fix round)

**交付**：`834fa34`（抽 `app/refdata_yaml.py`：6 个通用助手 + **必填 keyword-only `doc_kind`**，`refdata_prescription.py` 改成 5 个薄适配器 + 1 个别名，闸 A 5 条守卫；**956 → 961**）、`f08e9ce`（`data/alert_rules.yaml` + `app/domain/alerts.py` + `app/refdata_alerts.py` + 65 条测试；**961 → 1026**）、`caf80c5`（变异取证 5 条 × 三重还原 + 报告 + 行尾归一）。

**验收（控制者本机亲跑复核，探针 `t6_probes/_verify.py` 已入库）**：
- 全量 **956 → 1026 passed**（+70 = domain 35 + 加载器 35）；带 `--cov` **1025 passed, 1 skipped**
- **`app/domain/` 四格 996/0/288/0 → `1147 stmts / Miss 0 / 336 branch / BrPart 0 / 100%`** —— **stmts 与 branch 都涨了，而 `Miss` 与 `BrPart` 仍是 0、覆盖率仍是 100%**（spec §12 的硬要求兑现）。`app/domain/alerts.py` 自己 **151 / 0 / 48 / 0 / 100%**
- **扫描面 51 → 52**（pipeline 8 + db 11 + domain **17** + api 16）—— **只涨 domain 一格，与 P6-A3 的预测逐字相符**；`refdata_yaml.py` / `refdata_alerts.py` 都**不在** `SCANNED_DIRS`，故扫描面不因它们而涨 ✓
- 表数 **25**（未建表）；`_MODELS_PUBLIC_BASELINE` **33**（`models.__all__` 仍 14）；openapi paths 仍 **56**（operations 84）
- **P6-A1 + 顶回 3/4/5 全部落地亲验**：`StudentSignals` **11 字段** = `student_id / semester_id / week / rpe_streak / rpe_session_ids / mini_test_scores / mini_test_ids / checkin_gap_days / checkin_gap_end / completion_rate / mini_test_improved`（**顶回 4 的 `checkin_gap_end` 与顶回 5 的 `semester_id`/`week` 都在**）；`ClassSignals` **5 字段** = `course_section_id / semester_id / week / mean_rpe / student_count`；**`StudentHit` 与 `ClassHit` 都是 5 字段 = `rule_id / level / subject_key / window_key / snapshot`**（顶回 3 的 `subject_key` 在两个 Hit 上）
- `alerts.py` 的 `__all__` = **16** 个名字；`_ALERTS_PUBLIC_BASELINE` **`assert len(...) == 19`**（`app.domain.alerts` 16 + `app.refdata_alerts` 3）；`refdata_alerts.py` 照 P6-A5 **不写 `__all__`** ✓
- **P6-A2 落地亲验**：`app/refdata_yaml.py` 的 6 个函数 = `line_index` / `fail` / `exact_keys` / `as_int` / `as_float` / `as_optional_text`，**其中 5 个都有必填 keyword-only `doc_kind`**（`line_index` 没有，因为它只吃 `text`、报错时不涉及文档种类——**正确**）；`refdata_prescription.py` 只改了 3 处（docstring + 一行 import + 141 行的 6 个定义换成 49 行适配器块，diff **+49 / −126**），**57 处调用点一个字没动**（AST 实测），报错文本逐字不变
- **顶回 6 落地亲验**：`alerts.py:545` 是 `sig.completion_rate >= float(rule.params["completion_rate_min"])`，而 `:523` 的注释逐字写着「YAML 的参数名逐字是 `completion_rate_min`——一个叫 `_min` 的阈值被 `==` 消费自相矛盾」
- **`alert_rules.yaml` 亲验**：**6 037 B / CRLF 0 / sha256[:16] = `E48E3AC82BB45BB7`**；`version` 那一行原始文本逐字是 `version: "1.0"`（**带引号**，P6-A5 的要求兑现）
- **禁区**：三个既有指纹逐字不变；**`git diff a8d61b4 HEAD --name-status -- backend/data` 只有一行 `A backend/data/alert_rules.yaml`**（控制者用 `--name-status` 逐行比对，不是看它是否为空）；`pe.db` 不存在；`data/seed/` 0 文件
- **变异取证 5/5**（本 Task 的硬要求）：M1–M5 分别让 **3 / 9 / 6 / 2 / 5** 条测试红，**每条都靶命中且邻居保持绿**（M1 只让「坐在恰好 5%」那一格红，5.1% 与「更早的下降不算」两条仍绿；M4 最干净，只红 2 条，`mean_rpe=None` 与 `10.0` 仍绿）。**三重还原全部通过**：sha256 复原 `BF36B469F0FC19C9`（5/5）、`git diff` 该文件输出长度 **0**、复跑 `70 passed`；改完删了 `backend/app` + `backend/tests` 全部 `__pycache__`（硬规矩 #83），还原用 python 从 TEMP `write_bytes`（**不用 `git checkout`**）。收尾全量复跑 **1026 passed**

### Ruling 16 — 实现者顶回 8 处（3 条 Critical），**全部采纳**（Plan 03 的第 26–33 次；累计 **58 次，58 次都对**）

**顶回 1（Critical，采纳 → 控制者错误 #26）**：**P6-A2 漏了 `_fail` 的硬编码前缀。** 实测 `refdata_prescription.py` 的 `_fail` 末行逐字是 `f"处方模板 {path} {where}：{message}"` —— **原样共用会让 `alert_rules.yaml` 的报错说「处方模板 …/alert_rules.yaml 第 3 行」**，而 Review Focus 第 5 条要的正是「指出是哪个文件」，**那句话当场变成谎话**。实现者的处置：给 5 个助手各加一个**必填 keyword-only `doc_kind`（无缺省值）**。
**⚠️ 控制者的 P6-A2 说「把那 6 个搬进去、两处都从它 import」，却没有读那 6 个函数的函数体** —— 只读了签名。**这与 Plan 02 的控制者错误 #137 同型**（「派单说 `percentile.py` 里有一处先例是『触私有名』，而恰恰相反，那个文件明写『不 import 私有名』」）：**都是「引用一个既有实现的做法，却没读它的实现」。**

**顶回 2（采纳 → 控制者错误 #27）**：**`_PRESCRIPTION_PUBLIC_BASELINE` 实测是 51，不是派单说的 24。** 控制者亲验坐实：`assert len(...) == 51` 且 `app.domain.prescription.__all__` 实测 **51** 个。**而且它钉的是 `app.domain.prescription.__all__`（`_OWNED_MODULES` 九个模块 + `Layer`），与 `refdata_prescription.py` 的公开面无关** —— 后者 8 个公有函数今天没有任何基线钉它。**结论（「不动」）采纳，理由换掉。**
**⚠️ 这是「复用历史数字」的第 6 次**（Plan 02 的 #126 / #144 / #156、Plan 03 的 #7 / #8，本次 #27）—— **24 是 Plan 02 Task 4 结案时的值，之后 Plan 02 的 Task 5/6/7/8 各加过名字，而控制者在 Plan 03 Task 6 的派单里把它当成现值抄了进去。**
**→ 补硬规矩 #111：派单里出现的每一个「既有常量/基线的当前值」，必须在**当前 HEAD** 上实测一次；凡是能从更早的账本、报告或自己的记忆里读出来的数，一律视为过期。** 依据：#27；与 #89（运行时口径）配套 —— #89 管「怎么数」，#111 管「什么时候必须重数」。

**顶回 3（Critical，采纳）**：**`subject_key` 缺失。** 实测 `app/db/models/feedback.py`、`app/api/schemas/alerts.py`、`tests/db/test_models.py` **三处已落地代码**逐字把它的算式钉为「唯一所有者是 `app.domain.alerts`」，而它是 `uq_alert_rule_subject_semester_window` 的一列（控制者亲验：4 列 = `rule_id / subject_key / semester_id / window_key`）；**而计划的 Interfaces 只给了 `window_key`**。⚠️ **附带发现**：`subject_key` 是 `String(24)`，故前缀必须是 `section` 而不是 `course_section`（控制者亲验：`section:2147483647` = **18** 字符 ≤ 24 ✅；`course_section:2147483647` = **25** 字符 → **超宽 1**）。
**⚠️ 实现者报告里写的是「27 字符、超宽 3」，控制者实测是 25 / 超宽 1** —— **结论一致（前缀必须是 `section`），但它的两个数都错了 2**。这是纯散文精度问题（代码是对的），**归 Task 9 的勘误清扫，不返工**（Ruling 1 的口径）。**→ 控制者错误 #28 的反面：这是实现者的第 1 次散文数字错**（Plan 02 的实现者 3 次错误全部自纠，本次是第 4 次，且**没有被它自己抓到**）。

**顶回 4（Critical，采纳）**：**`checkin_gap_end` 缺失** —— `YELLOW_CHECKIN_GAP` 的 `window_key` 逐字要「中断结束日的 ISO 串」，而 `StudentSignals` 一个日期字段都没有；**P6-A4 只给了处置倾向（「控制者倾向把日期字段换成调用方已算好的 `str`」）却没把字段加进清单**。

**顶回 5（Critical，采纳）**：**`StudentSignals.semester_id` / `week` 缺失** —— `GREEN_MASTERY` 是 **student** 作用域（**计划自己给的 YAML 逐字 `scope: student`**）而它的 `window_key` 是 `semester_id:week`；**P6-A1 只给 `ClassSignals` 补了这两个**。

**⚠️ 顶回 3/4/5 是同一条纪律（硬规矩 #110）的三次应用**：把 P6-A1 自己的判据（「定义输出结构时逐字段回问这个值从哪个入参来」）在**两个去重键**上逐字段跑一遍，缺的 4 个字段就自己浮出来了。**控制者立了 #110、并在 P6-A1 里用了一次，但没有把它系统地跑完** → **这与控制者错误 #24 的形状相同（刚立完规矩就违反）**，是 Plan 03 的第 3 次（前两次：#107 立完十分钟就犯、#24）。
**→ 硬规矩 #110 扩写：立完一条新规矩的当轮，必须把它**系统地**跑一遍当前 Task 的全部相关对象（不是一个例子），并把「跑了几个、各查出什么」写进账本。只在一个例子上用过，等于没立。**

**顶回 6（采纳，且它是本轮最有价值的一处）**：**`GREEN_MASTERY` 用 `>=` 而不是计划正文的 `==`。** 三条理由全部成立：① **参数名逐字是 `completion_rate_min`，一个叫 `_min` 的阈值被 `==` 消费自相矛盾**；② `completion_rate ∈ [0,1]`，故 `>= 1.0` 与 `== 1.0` **对任何合法输入逐格等价**，spec 的「100%」没被放宽；③ **写成 `==` 会让本 Task 唯一要求的变异对第 5 条规则没有靶子**（`==`→`>=` 在 `[0,1]` 上不可分辨）。**M5 实跑红 5 条就是这条顶回的证据。**
**⚠️ 这一条的形状值得记**：控制者写的判据**语义上没错**（`==1.0` 与 `>=1.0` 在定义域内等价），**但它会让守卫失去牙齿** —— 而「守卫有没有牙」正是硬规矩 #92 管的事。**故 #92 的完整形态是：不仅「要求一条测试变红前先论证破坏在结构上可达」，还包括「写判据时优先选那个能被变异区分的形状」。**

**顶回 7（采纳）**：**「留痕」没有出口。** 计划要 `insufficient_points` 进 `snapshot`，但**不触发就没有 Hit、也就没有 snapshot**；而 `points_needed` 是 YAML 参数，故「够不够点」必须在 domain（否则 Task 7 要再读一次那个阈值 = **第二个所有者**）。实现者的处置：**每个求值器返回 `(命中, 留痕)` 一对**，新增 `student_skip_traces` / `class_skip_traces` 取后半 —— **「什么时候判不了」在代码里只有一处**。

**顶回 8（采纳）**：**P6-A2 的「两处都从它 import」落地成「各留 5 个一句转发的薄适配器 + 1 个别名」**，而不是改 57 处调用点。理由成立：**57 处逐点加关键字参数 = 57 次改坏一条被测试逐字钉住的报错文本的机会**。**逻辑仍只有一份**，单一所有者由 **AST 机器守**（定义点唯一 + 函数体恰好一句且在调谁 + `is` 身份比对）。

### 7 处偏离派单字面：全部追认

① `refdata_prescription.py` 的改法（= 顶回 8 的落地形状，**删的是实现层不是绑定层**）；② `alert_rules.yaml` 在逐字数据之外加了 33 行注释（**数据部分逐字不变**，由 `_SPEC_PARAMS`/`_SPEC_LEVELS`/`_SPEC_SCOPES` 三个字面量对账）；③ `tests/test_refdata_alerts.py` 的闸 A 6 条不在派单的 Create 语义里（**它是 P6-A2 的唯一机器守卫，没有别的自然住址**）；④ 加载器多做了 **4 类计划没要求的校验**（YAML `scope` 与 `declared_scope()` 对账、比率/计数取值范围、`points_needed == consecutive + 1`、计数必须是 `int` 而非 `float` —— **四类的共同点是失效静默**）；⑤ 变异跑两个测试文件（70 条）而非全量，收尾另跑两次全量确认；⑥ 5 个新 `.py` 的工作树行尾 LF→CRLF（**`git hash-object` 双向取证 blob 逐字不变、`git diff --cached` 为空**；`alert_rules.yaml` 刻意不在名单里）；⑦ `AlertLevel` ↔ `Alert.LEVELS` 那条断言住在 `tests/domain/test_alerts.py`（派单没指定住处）。

### 待清扫：**5 条**（纯散文精度，无 Critical）

① `refdata_prescription.py` 的 `equivalence()` docstring 说「本模块公有函数是 **5** 个」，AST 实测 **8** 个（**Plan 02 Task 3 留下的**）；② `tests/domain/test_prescription_templates.py` 说行号索引的实现在 `app.refdata_prescription._line_index`，**那个实现今天住在 `app/refdata_yaml.py`**；③ `refdata_prescription.py` 模块 docstring「两段的报错口径刻意不同」那段没指向 `app/refdata_yaml`；④ `refdata_alerts.py` 的 `_as_optional_text` 适配器今天没有调用者（docstring 已写明保留理由）；⑤ **阈值个数口径：派单与计划都说「8 个」，运行时实测 9 个**（逐条 3/2/1/1/2），**代码与测试一律用 9** → **控制者错误 #29**（又一次自己数错，与 #7/#8/#27 同族）。

### ⚠️ 控制者错误 #29 与本轮自查出的第 4 次路径深度错

**#29**：派单与计划都说预警阈值是「8 个」，实测 **9** 个（`RED_MINITEST_DROP` 3 个 / `RED_RPE_SUSTAINED` 2 / `YELLOW_CHECKIN_GAP` 1 / `YELLOW_CLASS_RPE_HIGH` 1 / `GREEN_MASTERY` 2）。**根因与 #7 相同：数的时候把「规则数 × 平均参数数」估了一下，没有逐条数。**

**⚠️ 第 4 次路径深度错**：本轮的亲验探针 `_verify.py` 又写了 `ROOT = HERE.parents[2]`（应为 `parents[3]`，因为它在 `t6_probes/` 下、比 `_t6_preflight_patch.py` 深一层），**当场让 `assert BACKEND.is_dir()` 红**（报出 `…\.superpowers\backend`）。前三次：`t3_probes/_verify.py`、`t4_probes/_preflight.py`、以及本轮的 `t5_probes`（那次是 `parents[4]` 写对但 `_t5_close.py` 的 `parents[2]` 也需复核）。
**⚠️ 每次都靠那条 `assert` 当场抓住、没有一次产生错误结论** —— 这正是硬规矩 #82（「探针的每一个前提都要有一条会红的断言」）的正面回报。**故不立新规矩，只记一笔：`assert BACKEND.is_dir()` 这一行是本项目里性价比最高的一行代码。**

### ⚠️ 按硬规矩 #86 回扫 Task 7/8/9 与 Plan 04（实现者给的 6 条关切，控制者逐条裁定）

1. **Task 7**：**`*_skip_traces` 必须有消费者**（顶回 7 的产出）。裁定：**Task 7 把 `student_skip_traces` / `class_skip_traces` 的计数写进 `daily_sync_run` 的日志或 `alert` 的 `trigger_snapshot` 之外的一个运维字段**；若无处可放，**至少要有一条测试断言它们被读过**（否则就是死配置，与 Plan 02 的 `Intensity.rpe` 同型）。
2. **Task 7**：**`rpe_session_ids` 必须按时间升序**（domain 只校长度、校不了顺序）→ **Task 7 组装 `StudentSignals` 时要按 `submitted_at` 排序，并加一条测试钉住**（乱序会让 `window_key` 取到错误的 `class_session_id`，从而让去重键失效 → 同一学生重复触发 → `0.8³`）。
3. **Task 7**：**`rpe_min` 与 `improve_pct` 由 Task 7 消费，不读就是死配置**（`rpe_min` 是「连续 ≥ 9」的那个 9，Task 7 要自己数连续；`improve_pct` 是「提高 ≥ 10%」，Task 7 要自己算 `mini_test_improved`）。
4. **Task 7**：**`completion_rate` 必须夹在 `[0,1]`**（`GREEN_MASTERY` 的 `>=` 与顶回 6 的等价性论证都建立在这个前提上；**越界会让 `>=1.0` 与 `==1.0` 不再等价**）。
5. **Task 7**：**`checkin_gap_days` 的「应打卡训练日」语义有一半住在调用方**（domain 只收一个整数）→ Task 7 要复用 Task 5 的 `_training_days_of()`，**不要另写一份**。
6. **Task 8/9**：**`AlertRules.params_of` 今天没有生产调用者**（留给 Task 7）；**Task 9 的勘误要收 5 条待清扫 + 顶回 3 的两个数（27/超宽3 → 25/超宽1）+ #29 的阈值个数（8 → 9）**。

**下一步**：抽 `task-7-brief.md` → 派实现者（预警落地 + `InAppChannel` + `weekly_adjustment` 的 `auto` 来源）。

---

## ✅ Task 7: complete (commits 6d0c8d2..5fe289c, 0 fix round)

**交付（5 个 commit，派单建议 3–4 个）**：`7228868`（`app/notify.py`：`NotificationChannel` Protocol + `InAppChannel` + 两个未来通道骨架，**值域与模型类常量对账、import 期响亮失败** + 14 条测试）、`6dc46a7`（**前置重构**：`_training_days_of` 从 `app/api/routers/feedback.py` 搬到 `app/pipeline/prescription_stage.py::training_days_of` —— 守卫禁止 `pipeline` import `app.api`；**零行为变更**）、`480a36e`（`app/pipeline/alert_stage.py`：组装 Signals → 调 domain → 落 alert → 发消息 → 写 `weekly_adjustment` 的 `auto` 来源 + 33 条测试 + **3 条变异自证**）、`196a00e`（Alert 阶段接进 `daily.py`：阶段序列 6→7、`run.alert_count`、`_replay_cleanup` 5→6 张 + `POST /api/alerts/{alert_id}/handle` + 24 条测试）、`5fe289c`（报告 + 7 个探针 + 清掉自查出的 2 个死 import）。
**多出的那个 commit 是 `training_days_of` 的搬家**（改的是 Task 5 的文件、零行为变更，**混进 ② 会让评审看不清哪一半是重构**）—— 控制者追认这个切分。

**验收（控制者本机亲跑复核，探针 `_t7_verify.py` 已入库）**：
- 全量 **1026 → 1097 passed**（+71 = notify 14 + alert_stage 36 + alerts_api 21），**零回归**
- `app/domain/` 四格 **1147 / Miss 0 / 336 / BrPart 0 / 100% 逐字未变** ✓（带 `--cov` 时 `1096 passed, 1 skipped`）
- **扫描面 52 → 54**（pipeline 8→9、db 11、domain 17、api 16→17）；**`/api/` 路径模板 56 → 57、操作数 84 → 85**（新增 `POST /api/alerts/{alert_id}/handle`，控制者从 `openapi()` 实读）；表数 **25**；`_MODELS_PUBLIC_BASELINE` **33**
- **`_replay_cleanup` 的清单控制者用 AST 口径亲验**（不用文本计数，#103/#107）：`['models.DerivedMetrics', 'models.StratificationResult', 'models.PercentileSnapshot', 'WeeklyAdjustment', 'Prescription', 'Alert']` = **6 张** ✅；**`ClassSession` 确实不在里面** ✅；**`WeeklyAdjustment`(#3) 在 `Prescription`(#4) 之前**（子表先删，Plan 02 的 P7-A4）✅
- **`AlertReport` 6 字段**（简报的 4 个 + `skipped`（P7-A3 第 1 条要求的）+ `errors`）；`AUTO_REDUCTION_FACTOR = 0.8`；`AUTO_SOURCE = 'auto'`
- **三个新模块的公开面**：`alert_stage` **9** 个、`notify` **8** 个、`api/routers/alerts` **5** 个；`refdata_alerts` 实测 **3** 个（`ALERT_RULES_FILENAME` / `alert_rules` / `load_alert_rules`）
- **`training_days_of` 只有一份定义**（控制者用 AST 数定义份数 = **1**，#89 再扩写）✅
- **禁区**：**四个指纹逐字不变**（三个既有 + Task 6 新增的 `alert_rules.yaml` = `E48E3AC82BB45BB7`，CRLF 均 0）；`git diff 6d0c8d2 HEAD -- backend/data` **为空**；`pe.db` 不存在；`data/seed/` 0 文件；架构守卫全绿

### Ruling 17 — 实现者顶回 5 处，**全部采纳**（Plan 03 的第 34–38 次；累计 **63 次，63 次都对**）

**顶回 3（Critical，采纳 → 控制者错误 #30）：RPE 的排序键应是「课次时间」`(session_date, period)`，不是派单写的 `submitted_at`。⚠️ 按派单的方子反而会引入它要防的那个失效。**
失效序列（实现者给的，控制者复核成立）：`submit_rpe` **刻意不做过期**（它 docstring 的「刻意不做」第 2 条），故**一节早先的课完全可以在一节晚近的课之后才被提交**。那时按 `submitted_at` 排会把 `S0` 插进 `[S1,S2,S3]` 的**前面** → `window_key` 的锚点从 `S3` 移到 `S2` → **键变** → 同一次「连续 ≥ 9」**第二次落库** → 减量系数连乘回来（正是 Review Focus 第 3 条要防的 `0.8³ = 0.512`）。
落地：`.order_by(ClassSession.session_date, ClassSession.period, RpeRecord.submitted_at, RpeRecord.id)` —— **`submitted_at` 与 `id` 只作同节课内的 tie-breaker**。**变异 M2 取证：只有该抓它的那一条红（1 failed / 32 passed）。**
**⚠️ 这一条的性质**：控制者从 Task 6 的关切里逐字抄了「`rpe_session_ids` 必须按时间升序」，**并自作主张指定了「按 `submitted_at` 排序」** —— 而「时间」在这个语境里有两个候选（课次时间 vs 提交时刻），**控制者选了错的那个，且它不是「不够好」而是「会引入失效」**。
**→ 补硬规矩 #112：传导一条纪律时，只传「要满足什么性质」（如「按时间升序」），不要替实现者指定「用哪一列」——除非控制者已经核实那一列在该语境里就是那个性质的唯一载体。** 依据：#30。**⚠️ 这与硬规矩 #98 是一对**：#98 说「要求 X 时必须给出怎么做到 X 的机制」，#112 说「给出机制时不要给错的那一个；给不出正确的就只给性质」。**两条合起来是：机制要么给对，要么不给。**

**顶回 4（Important，采纳）：`reason` 不带 YAML 版本号**（与 `app/domain/alerts.py` 模块 docstring 那一句相反）。理由是一条具体的失效：**`reason` 是那条四列唯一约束的一列**，把版本号拼进去（`"RED_RPE_SUSTAINED@v1.0"`）会让「专家升一次 YAML 版本号」**等价于「同一周可以再减一次量」** → `0.8 × 0.8 = 0.64`，**而 Review Focus 第 3 条要防的连乘从版本号那一侧回来了**。约束自己的注释也逐字警告过「`reason` 是自由文本，改一个标点就绕过了本约束」。
落地：**版本号改落 `alert.trigger_snapshot["alert_rules_version"]`** —— 预警行与调整行是**同一次触发**的两半（同一条规则、同一周、同一个学生），故「当时按哪一版阈值判的」仍可离线复核，**可追溯性无损**。
**⚠️ 连带**：`app/domain/alerts.py` 的模块 docstring 那一句现在是错的 → **归 Task 9 的勘误**。

**顶回 1（Important，采纳 → 控制者错误 #31）：`_replay_cleanup` 的元组在 HEAD 上已经是 5 项、不是 3 项。** 派单的 P7-A2 把 **Plan 02 Task 7 早做完的扩表**当成本 Task 的活，并引了 `daily.py:755` 那条注释作证据 —— **而那条注释自己就是过期的**（它说「Task 7 把 `_replay_cleanup` 扩到五张之后就过期了」，而那次扩表在 Plan 02 就发生了）。**⚠️ 这是硬规矩 #111 的第 2 次违反**（「派单里每一个既有常量的当前值都要在当前 HEAD 上实测」）—— 控制者实测了它**存在**，但没实测它**当前的长度**，而是照注释里的数字推理。

**顶回 2（Important，采纳 → 控制者错误 #32）：扫描面 52 → 54，不是派单预测的 53。** 派单漏算了 `app/api/routers/alerts.py` —— **而那是派单自己在第 4 节逐字要求本 Task 创建的**（S1 的裁定），且 `api` 在 `SCANNED_DIRS` 里。**⚠️ 同一份派单的两节互相矛盾，控制者没有在写完后回读一遍。**

**顶回 5（Minor，采纳）：`checkin_gap_end` 锚在「凑满 `gap_days` 那一天」，不是 domain docstring 字面的「中断的**结束日**」。** 按字面读法**键会天天变**，一个 5 天的中断会落 **4 条 alert** —— **Review Focus 第 3 条从打卡侧回来了**（与顶回 4 是同一条纪律在另一条规则上的应用）。

### 3 处偏离派单字面：全部追认

① `evaluate_alerts` 多了 3 个 keyword-only 形参（`exercises` / `now` / `channel`）—— **简报那个签名跑不起来**（`triggered_at` 与 `created_at` 都是 NOT NULL 无缺省，`training_days_of` 要动作库）；② `AlertReport` 是 6 字段不是 4（`skipped` 是派单 P7-A3 第 1 条**要求**的；`errors` 是异常分层的可观测量）；③ skip 留痕的日志落在 `alert_stage` 而**不是** `run_daily`（照 `generate_prescriptions` 的既有先例：阶段自己印自己的计数；`main()` 的 CLI 另补了一行「预警：本日新触发 N 条」）。

### ⚠️ 实现者报的三件事，控制者逐条裁定

**① 撞红的既有守卫只有 1 条，且不是派单预测的那一条。** 派单预测 `tests/api/test_crud.py` 的路由数断言会红；**实际红的是 `tests/api/test_prescription_api.py::test_the_identity_headers_are_registered_as_openapi_security_schemes` 的第 ③ 拍**（「除特例清单外 `/api/` 下不带 security」）。**那条守卫的 docstring 逐字写着「Task 7/8/9 每加一个带身份的特例端点都要回来加一行——这是有意的」**，故按其设计登记（11 → 12 项）。`test_crud.py` 一条都没红。**⚠️ 这又是一次「控制者预测的红点不是真的红点」**（与 Plan 02 的 #138 同族：控制者凭记忆点名一个位置，而真的在另一处）。

**② 求值人群这个决定是性能实测驱动的，代价如实记录。** 人群 = **本学期在三源里留过痕的学生**。理由：`GREEN_MASTERY` 与 `YELLOW_CHECKIN_GAP` 都要 `training_days_of`（= 装配训练包），**全员求值会让 `test_backfill`（500 人 × 112 天）多跑约 56 000 次装配**，而那条 `elapsed < 90` 在 Task 5 结案时全量跑实测已到 **47.33 / 47.96 s（余量仅 1.88×，低于硬规矩 #42 的 2× 线）**。**本 Task 实测 `elapsed = 31.63 s`**（单跑，取证照账本 Ruling 12，跑完按字节还原并复核），Alert 阶段约 **+2 s**。
**控制者裁定：采纳这个人群口径**，并**如实记录代价**：**一个本学期从没在任何一源留过痕的学生不会被求值** —— 而这类学生恰恰可能是最该被关注的（长期缺席）。**但 `YELLOW_CHECKIN_GAP` 的语义是「连续 N 个应打卡训练日未打卡」，一个从没留痕的学生没有「应打卡训练日」的基线可算**（分母来自他本周的训练单），故**这不是本 Task 的取舍失误，而是这条规则的定义边界**。**→ 记进 Task 9 的 spec 勘误：`YELLOW_CHECKIN_GAP` 只对「本周有训练单」的学生可判。**

**③ 实现者自己发现了一格派单没点出来的东西（控制者认为这是本轮最有价值的一处）**：打卡那一源用了**两个不同的窗口** —— 喂**信号**的按三周回看，喂**人群**的只按 `semester.start_date`。**用同一个窗口会漏掉最该被提醒的人**：连续失联四周的学生在三周窗口里**一行都没有** → 不在人群里 → `YELLOW_CHECKIN_GAP` 对他**永远不触发**，而那正是这条规则存在的理由。
**⚠️ 这一条的形状值得记**：它不是「派单错了」也不是「守卫不够」，而是**「两个看起来该用同一个参数的地方，其实需要不同的参数」** —— 与 Plan 02 的控制者错误 #5（「枚举分桶的 6 个结果」被当成「分层判定的 3 个结果」）同族，但方向相反：**那次是把两个东西当成一个，这次是发现了两个东西不能当成一个。**
**→ 补硬规矩 #113：一个查询窗口/阈值/人群口径被两处使用时，先问「这两处要回答的是同一个问题吗」；若不是，它们需要两个参数，而共用一个会静默地让其中一处失效。** 依据：本条；Plan 02 的 #5。

### 待清扫：**4 条**（全无 Critical）

`repo.py::delete_by_batch` 的两处过期计数（「清的是九张里的五张」、「Alert 由 Task 8 接进」——**Alert 本 Task 已接进**）｜`models/feedback.py` 模块 docstring 与 `Alert.batch_id`/`Notification.alert_id` 列注释里的「Task 8」｜`prescription_stage.py` 的「`auto` 也留给 Plan 03」与「生产写入方今天仍为零」（**本 Task 已落地**）｜`api/routers/feedback.py` 的 **4 个死 import**（用 `git show 6d0c8d2` 复核过，**基线上就有**，不是本 Task 造成的）。
**⚠️ 前三条都是「散文说某个活留给后面的 Task，而那个活已经做完了」** —— 与硬规矩 #97 同族（一个改动会让别处的事实过期）。**归 Task 9 的勘误一并清。**

### ⚠️ 按硬规矩 #86 回扫 Task 8/9 与 Plan 04

1. **Task 8**：`_replay_cleanup` 现在是 **6 张**，本 Task 加的是 `Alert`；**Task 8 要加 `WeeklyClassReport`（→ 7 张）**，且**子表先删的纪律仍适用**（`WeeklyClassReport` 没有子表指向它，故排在哪都行，但**要有一条测试钉住清单的长度与成员**，否则下一个人加表时会静默改变重放语义）。**⚠️ `notification` 不进清单**（它不带 `batch_id`），它的 `alert_id` 带 `ondelete="SET NULL"`，故删 `alert` 不会让通知行炸 FK。
2. **Task 8**：`api/routers/alerts.py` **已由本 Task 创建**（S1 的裁定兑现），Task 8 只 **Modify** 它（若要加端点）。**⚠️ 特例路由必须在 `catalog` 之前 include**（Task 5 顶回 5 立的规矩）。
3. **Task 8**：`training_days_of` 现在住在 **`app/pipeline/prescription_stage.py`**（不再是 `app/api/routers/feedback.py` 的私有函数）→ Task 8 的班级周报若要算训练日，**从这里 import，不要另写一份**（AST 守卫 `test_training_days_of_has_exactly_one_definition` 会抓）。
4. **Task 9 的勘误清单新增 4 条**：① `app/domain/alerts.py` 模块 docstring 里「`version` …… Task 7 把它写进 `weekly_adjustment` 的 `auto` 来源留痕」那一句**是错的**（顶回 4）；② `YELLOW_CHECKIN_GAP` **只对「本周有训练单」的学生可判**（裁定 ②）；③ 上面那 3 条「散文说留给后面的 Task 而活已做完」；④ **`subject_key` 的宽度口径**：Task 6 的报告写「`course_section:2147483647` 是 27 字符、超宽 3」，控制者实测是 **25 字符、超宽 1**（结论一致：前缀必须是 `section`）。
5. **Plan 04**：`POST /api/alerts/{alert_id}/handle` 的三个动作值是 **`ACTION_REDUCE` / `ACTION_IGNORE` / `ACTION_NOTE`**（在 `app/api/routers/alerts.py`），前端要从 `/openapi.json` 读、不要抄字符串。

**下一步**：抽 `task-8-brief.md` → 派实现者（班级周报 + 大屏/首页聚合 + 教师端训练单变体）。

---

## ✅ Task 8: complete (commits 6127fc7..d100ff5, 0 fix round)

**交付**：`6b5decc`（`app/domain/report.py` —— 周报与大屏**共享**的九个聚合量，纯函数、100% 分支覆盖、**24 条变异全 killed**）、`e593532`（Report 阶段接进 `daily.py`：周日判据 + **与 Alert 阶段共享同一个 `now`** + `_replay_cleanup` 6→7 张）、`415db83`（大屏/首页聚合读接口 + **P8-A5 的教师端训练单变体** + 通知已读，security 清单 12→17）、`d100ff5`（报告 + 派单 + 7 个探针）。

**验收（控制者本机亲跑复核，探针 `_t8_verify.py` 已入库）**：
- 全量 **1097 → 1225 passed**（+128 = `test_report.py` 55 + `test_report_stage.py` 35 + `test_daily.py` 2 + `test_dashboard.py` 36），**既有 1097 条一条都没退步**；带 `--cov` **1224 passed, 1 skipped**
- **`app/domain/` 四格 1147/0/336/0 → `1259 stmts / Miss 0 / 376 branch / BrPart 0 / 100%`** —— **`Miss` 与 `BrPart` 仍是 0**，stmts +112 / branch +40 **恰为 `report.py` 一个文件的量**（P8-A2 的裁定兑现了：聚合逻辑进了 domain，故它被 100% 分支覆盖）
- **扫描面 54 → 58**（pipeline 9→10、db 11、domain 17→18、api 17→19）；**`/api/` 路径模板 57 → 62、操作数 85 → 90**（控制者从 `openapi()` 实读）；**挂 `security` 的操作数 12 → 17**；表数 **25**；`_MODELS_PUBLIC_BASELINE` **33**
- **五个新端点逐个亲验在线**：`GET /api/dashboard/class/{course_section_id}`、`GET /api/dashboard/weekly-class-report/{course_section_id}`、`GET /api/students/{student_id}/home`、`GET /api/teacher/students/{student_id}/weekly-sheet`、`POST /api/notifications/{notification_id}/read`
- **`app/domain/report.py` 的 `__all__` = 26 个名字**（10 个函数 + 1 个值类型 `RpeWeek`（字段 `days` / `values`）+ 15 个常量）
- **`_replay_cleanup` 的清单控制者用 AST 口径亲验 = 7 张**：`models.DerivedMetrics / models.StratificationResult / models.PercentileSnapshot / WeeklyAdjustment / Prescription / Alert / WeeklyClassReport`；**`ClassSession` 确实不在里面**；**`WeeklyAdjustment` 仍在 `Prescription` 之前**（子表先删）
- **`training_days_of` 定义份数 = 1**（AST 口径，P8-A3 兑现）
- **周日判据的三格边界测试**（日期一律字面写死、且都真的跑一遍 `run_daily`）：`test_a_saturday_does_not_generate_a_report`（2025-09-13 → 0 行）、`test_a_sunday_generates_a_report`（2025-09-14 → 1 行、`week == 2`）、`test_a_monday_does_not_generate_a_report`（2025-09-15 → 0 行）；另有 `test_the_report_weekday_constant_is_six_and_six_is_sunday`（**反证 `isoweekday()==6` 是周六**）、`test_is_report_day_over_one_whole_real_week`（七天逐个过）、`test_a_sunday_before_the_semester_starts_generates_nothing`（2025-08-31：`is_report_day` 为真而 `semester_week_of` 为 `None`，**两个判据不互相掩盖**）
- **禁区**：四个指纹逐字不变（CRLF 全 0）；`git diff 6127fc7 HEAD -- backend/data` **为空**；`pe.db` 不存在；`data/seed/` 0 文件；**`test_backfill.py` 已按字节还原**（实现者为取证 `elapsed` 临时改过阈值，控制者亲验 `git diff` 为空）
- **性能哨兵**：`elapsed` 实测 **43.96 / 48.37 s**（n=2，同口径基线 47.33 / 47.96），余量 **1.86×** vs 基线 1.88× —— **差异在 n=2 的组内极差（4.41 s）之内，没有可辨退化**

### Ruling 18 — 实现者顶回 4 处，**全部采纳**（Plan 03 的第 39–42 次；累计 **67 次，67 次都对**）

**顶回 3（Critical，采纳 → 控制者错误 #33）：P8-A5 那条授权链必须带学期，派单没说。** 派单写的是「`enrollment` 表 + `course_section.teacher_id` 是那条链」，**而没有要求两行的 `semester_id` 都等于 `as_of` 所属的那个学期**。**不带的后果**：判据退化成「他**曾经**教过这个学生」—— **上学期教过某人的教师，这学期仍读得到他本学期的训练单**。实现者落地的链是 `teacher.staff_no → teacher.id → course_section.teacher_id → enrollment.course_section_id → enrollment.student_id`，**且两行的 `semester_id` 都必须等于 `as_of` 所属的那个学期**。
**⚠️ 最值得记的是它自己说的这句：「这一格是被自己的测试抓到的，不是先想到的。」** 即**它先按派单写了、测试红了、才发现派单少了一格** —— 这正是 TDD 的回报，也是 Ruling 5（独立评审席折进控制者亲验）唯一还站得住的理由：**控制者亲验抓不到「控制者自己规定的东西是错的」，而实现者的测试能。**
**→ 补硬规矩 #114：派单里写「用 X 表 + Y 列做校验」时，必须同时写明**时间/学期的限定**——授权与归属类的判据几乎总是「在某一段时间内成立」，而「曾经成立」与「现在成立」是两个不同的判据。** 依据：#33。**⚠️ 这一族与 #112（「传导纪律时只传性质、不指定用哪一列」）是一对**：#112 管「不要给错的机制」，#114 管「不要给不完整的机制」。

**顶回 1（采纳 → 控制者错误 #34）**：`generate_weekly_reports` 的签名**跑不起来** —— 派单写 `(*, as_of)`，而 `generated_at` 是 `DateTime NOT NULL` 且无缺省、`training_days_of` 要 `exercises` → 补 `now` / `exercises`。**⚠️ 与 Task 7 顶回 `evaluate_alerts` 的签名是同型同理由**（`triggered_at` 与 `created_at` 都是 NOT NULL 无缺省）。**这是控制者连续两个 Task 犯同一个错**：写端点/阶段函数的签名时，**没有核那些 NOT NULL 无缺省的列由谁填**。
**→ 硬规矩 #98 再扩写：派单给出一个函数签名时，必须逐个核对它要写的表的 NOT NULL 无缺省列，每一列都要在签名里有一个来源（形参、或函数体里能从形参算出来）。**

**顶回 2（采纳）**：`ReportSummary` 加第三格 `errors`，并**给派单没定义的 `skipped` 定了口径**（= **名册为空的班**；并明确它**不是**「判不了」的垃圾桶）。**⚠️ 这与 Task 7 的 `AlertReport.skipped`（= `*_skip_traces` 的计数）是两个不同的 `skipped`** —— 同名不同义，**控制者裁定：两个都保留，但各自的 docstring 必须写明自己的口径**（否则下一个人会以为它们是同一个量）。

**顶回 4（采纳，且它报的成本比派单说的更高）**：P8-A6 的结论对（不加 `screen:` 段），但**成本比派单说的更高** —— `refdata_alerts.load_alert_rules` 的校验顺序是「**顶层键集** → version → rules 键集 → 逐条规则」，而**顶层键集是「恰好相等」的判据**，故加 `screen:` 段会**当场让加载器响亮失败**、必须再动一个 Task 6 已结案的守卫。**处置照派单办**（不加、四个指纹不变、阈值做 domain 常量并注明「待体育专家确认」）。**⚠️ 这一条说明控制者的 P8-A6 只算了「指纹要同步」这一项成本，漏了「加载器的键集校验是恰好相等」这一项** —— 与 #26（P6-A2 没读 `_fail` 的函数体）同族：**引用一个既有实现的做法，却没读它的实现。**

### 5 处偏离派单字面：全部追认

① **新增 `app/api/schemas/dashboard.py`（16 个响应模型）**，在派单的 Create 清单之外，**理由是 P4-A5「要确保后端和前端能够对接的上」** —— 控制者认为这是本轮最好的一处偏离：**没有响应模型，`/openapi.json` 里那 5 个新端点的 2xx 就是空的，前端 codegen 拿不到任何形状**（控制者亲验：2xx 响应带 schema 的比例见上面第 1 节）；② 多改 `deps.py` / `routers/prescription.py` / `schemas/__init__.py` 三个文件；③ `_replay_cleanup` 的 AST 断言放在 `test_report_stage.py` 而不是 `test_daily.py`（与 Task 7 把 `Alert` 那一条放在 `test_alert_stage.py` 同构）；④ **`test_daily.py` 的 `PIPELINE_TABLES` 刻意不加 `weekly_class_report`**（那条测试跑在周一，**加了是空转守卫**——硬规矩 #92 的正面执行）；⑤ **删掉 `generate_weekly_reports` 里一段自己第一版写的、实测不可达的学期存在性校验**。

### ⚠️ 变异取证 24/24 killed，其中两条的来历值得记

`report.py` 做了 **24 条变异、全部 killed**。其中 **M13 与 M23 两条是「先写测试 → 变异存活 → 补反例 → killed」的产物**，各对应硬规矩 #107（谓词先对已知反例验证）与**字符串驻留**。
**⚠️ 控制者裁定：这个形状（变异存活 → 补反例）比「一次就 killed」更有价值**，因为它证明的是「测试**曾经**抓不到、现在抓得到了」—— 而一次就 killed 只证明「这条变异在这个测试面前是可达的」。**→ 记进 Task 9 的勘误：把「变异存活过再补反例」当作一种正当的、要写进报告的取证形状，不是「测试写错了」的证据。**

### 待清扫：**6 条**（另有 4 条关切）

① `_stratification_payload` 是 `input_snapshot_of` 的**逆运算**，而正向那一份住在 `run_stratify.py`（**两个所有者，一正一逆**）；② **两档 404 的形状在 OpenAPI 里看不见**；③ **`daily_sync_run` 没有 `report_count` 列**（周报份数只有日志，而 `prescription_count` 与 `alert_count` 都有列 —— 三个阶段的可观测量不一致）；④ **教师侧「通知已读」今天没有端点**；⑤ **`mini_test.normalized_score` 仍只有 `demo_data` 一个写入方**（**进步榜在生产路径上会全员 `unmeasured`**）；⑥ 三个写入端点仍只过 `require_teacher`（没有任教关系校验）。
**⚠️ 第 ⑤ 条要传导给 Plan 04**：进步榜（`progress_board`）在真实数据下会全是 `unmeasured`，因为 `POST /api/mini-tests/batch` 今天**不算** `normalized_score`（Task 5 的 `GET /api/mini-tests/normalized` 是**读时算**、不写回列）。**故 Plan 04 的进步榜要调 `GET /api/mini-tests/normalized`，不要读 `weekly_class_report.progress_board`** —— 或者 **Task 9 要让 `report_stage` 在生成周报时把标准化得分算出来填进 `progress_board`**（控制者倾向后者，因为周报是快照、而快照里的量应该在生成时就算好）。

### ⚠️ 按硬规矩 #86 回扫 Task 9 与 Plan 04

1. **Task 9**：`_replay_cleanup` 现在是 **7 张**，钉住它的守卫是 `test_the_replay_cleanup_list_is_pinned_to_seven_tables`（**函数名里有「seven」**，Task 9 若再加表要连函数名一起改）。
2. **Task 9**：**`progress_board` 的填充口径要定**（见待清扫第 ⑤ 条）。
3. **Task 9 的勘误清单再新增 3 条**：① `require_teacher` / `require_scope` 里「原型没有教师↔班级↔学生授权模型」那两句**已被 Task 8 改写**（它连带收窄了班级那一侧），核实新文本是否如实；② **两个不同的 `skipped`** 各自 docstring 是否写明口径（顶回 2）；③ **`daily_sync_run` 三个阶段的可观测量不一致**（`prescription_count` / `alert_count` 有列，周报份数只有日志）。
4. **Plan 04**：① **`app/api/schemas/dashboard.py` 有 16 个响应模型**，前端 codegen 直接可用；② 教师端读学生训练单的路径是 **`/api/teacher/students/{student_id}/weekly-sheet`**（与学生侧 `/api/students/{student_id}/weekly-sheet` **响应体逐字相同**，因为 `weekly_sheet` 的函数体被抽成 `_weekly_sheet_response` 两处共用）；③ **进步榜走 `GET /api/mini-tests/normalized`**（见待清扫第 ⑤ 条）；④ `POST /api/alerts/{alert_id}/handle` 的三个动作值是 `ACTION_REDUCE` / `ACTION_IGNORE` / `ACTION_NOTE`。

**下一步**：抽 `task-9-brief.md` → 派实现者（GC14 + 端到端冒烟 + `demo.ps1` + spec 勘误）。**⚠️ 这是 Plan 03 的最后一个 Task，也是「能运行起来」的唯一可执行判据所在。**

---

### ⚠️ 控制者亲验跑出的一处「不符项」经复核是**探针工具选错**（控制者错误 #38，本计划第 6 次）

`_t9_close.py` 的第 4 节报了两条 ⚠️：「`demo.ps1` 含禁区命令 `seed.generate`（2 处）与 `pipeline.backfill`（1 处）」。按硬规矩 #109 用第二个独立工具（`Grep` 带上下文）复核，**坐实是假发现**：

那些字样**只出现在脚本自己的 docstring 里、用来解释「为什么本脚本一条 `python -m …` 都没有」** —— 逐字是「⚠️ **一条 `python -m …` 都没有**：`app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily` 三个 CLI 的 `main()` 各自把缺省值写死在**两个禁区**上（`backend/data/seed/` 与 `backend/pe.db`）。故本脚本一律调 `scripts/demo_bootstrap.py`，那里面是 import 函数 + 显式传路径」。另一处 `pe.db` 的命中是脚本**自己的禁区复核输出行**（`Write-Host "   禁区复核：backend\pe.db 不存在、backend\data\seed\ 仍为 0 文件 ✓"`）与两个守卫变量（`$ForbiddenDb` / `$ForbiddenCsv`）。

**⚠️ 这与 Task 5 结案时那次假发现（`'顺序今天不承重' in ri` 匹配到的是那句更正说明里对旧文本的引用）**完全同形**：谓词匹配到了「对某物的提及」，而控制者把它当成了「某物本身」。** 这是硬规矩 #109 立的理由，而它**第 2 次生效**（第 1 次是 Task 5 的 include 顺序）。
**→ 控制者错误 #38。⚠️ 本计划的 6 次探针工具错逐条**：#12（文本计数核一张数据驱动的表）、#22（`callable()` 把 Pydantic 模型类当函数）、#24（`str.find()` 量到 import 行的字母序 + 子串匹配到对旧文本的引用，**一次两处**）、路径深度错 **3 次**（`t3_probes` / `t4_probes` / `t6_probes`，每次都靠 `assert BACKEND.is_dir()` 当场抓住）、#38（本次）。
**→ 硬规矩 #109 扩写：谓词匹配到「文本里出现某个串」时，必须再问一句「这是**它本身**，还是**对它的提及**（docstring / 注释 / 更正说明里的引用 / 守卫变量名）」。判据是看命中行的上下文，不是看命中数。** 依据：#24 与 #38 是同一条谓词错误的两次发作。

**⚠️ 顺带核到实现者做得比派单要求的更多**（值得记）：`demo_bootstrap.py` **自带两道前置守卫** —— `--csv-dir` 撞上 `backend/data/seed` 或 `--db-url` 以 `pe.db` 结尾**都当场 `SystemExit`**；`demo.ps1` 还**自己印一行禁区复核**。**派单只要求「第一步删掉旧的 `pe_demo.db`、显式设 `PE_DB_URL`」，而它把禁区做成了脚本自己会拦的东西** —— 这与 Task 1 把 `api` 层预先加进守卫 allow-list、Task 8 主动加 `schemas/dashboard.py` 是同一种形状：**实现者在「满足派单」之外多做的那一格，往往是把一条纪律变成机器会拦的东西。**

### Task 9 亲验的其余各节全部通过 ✅

- 全量 **1244 passed**（控制者本机亲跑，121.79 s）
- 表数 **25**；扫描面 **60**（pipeline 10 + db 11 + domain 18 + api 21）；**`/api/` 路径模板 63、操作数 91、挂 `security` 的 18**；`/api/pipeline/run-daily` **在线**
- **黄金用例 14 个**（控制者亲验；⚠️ 顶层键是 `['_meta', 'input', 'expected']`，**用例列表在 `input` 那一格**，控制者第一版探针假定了键名叫 `cases` 故数出 3 —— **这是本轮的第 5 次探针工具错，与 #38 同一次跑出**）
- **`golden_cases.json` 51 619 B / CRLF 959 / bare LF 0**；as-is 指纹 **`39FC9C29D9106C47`**、CRLF→LF 指纹 **`9FB1C619F896D418`**（两个都与实现者报的逐字相同）
- **四个既有指纹逐字不变**；`git diff cf9ad7a HEAD -- backend/data` **为空**；`pe.db` **不存在**；`data/seed/` **0 文件**
- **标准化得分的单一所有者**：AST 亲验 `shuttle_percentile`（`app/domain/report.py:599`）与 `mini_test_scores`（`:654`）**各只有一份定义、都在 `app/domain/report.py`** ✅（派单说的「定义份数 == 1」是「**一个住址**」，而那一个住址里有**两个**函数定义，故守卫断言 2）
- **Ruling 20 的事实控制者用 `openapi()` 独立复核坐实**：`POST /api/class-sessions` 的 `security` **为空（匿名可写）**；而**挂了 `security` 的 9 个 POST 端点全部是特例端点**（`open-rpe` / `rpe-records` / `training-logs` / `mini-tests/batch` / `overrides` / `regenerate` / `alerts/…/handle` / `notifications/…/read` / `pipeline/run-daily`），**泛型 CRUD 的写入侧一个都没有** → 裁定归 Plan 04 的第一件事（见 Ruling 20）

**Task 9 结案口径**：**0 fix round**（唯一的「不符项」经查是控制者的探针错，不构成发现）。

---

## 🏁 Plan 03 全部 9 个 Task 完成

| Task | commit 区间 | passed | fix round | 顶回 |
|---|---|---|---|---|
| 1 FastAPI 骨架 + 作用域闸门 | `69b4218..2832a27` | 824 | 1 | 3 |
| 2 反馈与预警的 7 张表 | `bcf3936..fd73788` | 845 | 0 | 3 |
| 3 泛型 CRUD + 23 个资源 | `40a7a0e..e88afaf` | 876 | 0 | 7 |
| 4 处方侧四个特例端点 | `9062b37..95c7f76` | 910 | 0 | 7 |
| 5 §8.1 三源采集七个端点 | `acd3f53..c61dc3c` | 956 | 0 | 8 |
| 6 预警规则（5 条，变异 5/5） | `a8d61b4..caf80c5` | 1026 | 0 | 8 |
| 7 预警落地 + auto 来源 | `6d0c8d2..5fe289c` | 1097 | 0 | 5 |
| 8 班级周报 + 大屏/首页（变异 24/24） | `6127fc7..d100ff5` | 1225 | 0 | 4 |
| 9 GC14 + 端到端冒烟 + demo.ps1 | `cf9ad7a..4a8b792` | **1244** | 0 | 6 |

**最终状态**：**1244 passed**；`app/domain/` **1268 stmts / Miss 0 / 376 branch / BrPart 0 / 100%**；**25 张表**；**63 个 `/api/` 路径模板、91 个操作**；扫描面 **60**；**14 个黄金用例**；五个指纹逐字不变；`pe.db` 不存在、`data/seed/` 0 文件。
**顶回累计 73 次、73 次都对**（Plan 02 的 25 + Plan 03 的 48）；**控制者错误累计 38 条**；**硬规矩从 #94 增到 #115**；**Ruling 1–20**。

**下一步**：全分支终审（**Ruling 5 保留的那一席独立评审者**）→ `finishing-a-development-branch` → 写 Plan 04（Vue3 前端）。
