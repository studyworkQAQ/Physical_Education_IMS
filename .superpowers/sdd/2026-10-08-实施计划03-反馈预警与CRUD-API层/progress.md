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
