# Task 4 简报 — 处方侧的特例端点（教师覆盖 + 本周训练单 + 手动重生成）

> 本简报由控制者从 `Document/2026-10-08-实施计划03-反馈预警与CRUD-API层.md` 按**标题锚点**抽出，**逐字复制、未改写一个字**。抽的是：计划头部 + Global Constraints + Review Focus + File Structure + **Task 4 全节（含预检更正 P4-A1..A7）**。

## 0. 派单说明（控制者写，不在计划正文里）

**代码基线**：见 `git log --oneline -1`（分支 `feature/plan-03-feedback-alert-crud-api`，工作树干净）。
**测试基线**：`cd backend; python -m pytest -q` → **876 passed**。
**覆盖率基线**：`--cov=app.domain --cov-branch` → **996 stmts / Miss 0 / 288 branch / BrPart 0 / 100%**（带 `--cov` 时 `875 passed, 1 skipped`）。**本 Task 不加 domain 代码，四格应逐字不变。**
**表数 25**（`prescription` **16 列**）；`_MODELS_PUBLIC_BASELINE` **33（不动）**；扫描面 **49**；**HTTP 端点 47 个在线**。
**环境**：Python 3.11.1（无 venv）、SQLAlchemy **2.1.3**、FastAPI **0.141.1**、Pydantic **2.13.5**、httpx 0.28.1。
⚠️ **开工第一件事（硬规矩 #73）**：跑那条 import 冒烟并记进报告。**若撞上 `ImportError: DLL load failed`，立刻停手报回控制者。**

**⚠️ 控制者已经起过真实服务并用 httpx 打了一整圈 CRUD**（取证脚本 `t3_probes/_live_smoke.py`），全部符合预期：`POST` → 201 + `Location`、撞自然键 → 409 且消息点名键列、`PATCH` 部分更新且 `null` 与「没传」可区分、`forbid` → 405、只读资源 → 405、错误形状统一。**你不需要重跑这一圈**，但**你加的端点要符合同一套约定**（统一错误形状、`Location` 头、分页形状）。

**⚠️ 用户 2026-10-08 的原话是「要确保后端和前端能够对接的上」** —— 本 Task 的 P4-A5 与 P4-A6 两条就是这句话的落点，**不是可选的美化**。

## 0.1 ⚠️ 本 Task 的 1 条 Critical

**P4-A1：`WeeklySheet` 不能直接 JSON 化。** 控制者实测 `json.dumps(dataclasses.asdict(sheet))` 抛 **`TypeError: cannot pickle 'mappingproxy' object`**（`AssembledBlock.structure` 是只读映射，`asdict` 会 `deepcopy` 它）。**带不带 `default=str` 都失败**——`default` 只在「未知类型」时被调用，而 `asdict` 在**到达 json 之前**就炸了。

**处置**：不许用 `dataclasses.asdict`。**Plan 02 已经解决过同一个问题**——`app.pipeline.prescription_stage.training_package_payload(pkg) -> dict`（**已在 `__all__` 里**，实测签名就是这一个参数）就是「`TrainingPackage` → 可 JSON 的 dict」的投影，它已经处理了只读映射、三层嵌套与 `hr_zone` 的元组→列表。
**你要做的**：把它的 **block 级投影提成一个模块级函数**（如 `_block_payload(block) -> dict`），**weekly-sheet 与 training-package 两处共用**。
⚠️ **是「提取」不是「复制」**——复制会产生第二个所有者，而两个投影一旦漂移，**前端在学生端看到的 block 与教师端看到的就不是同一个形状了**。
⚠️ **要有一条测试钉住「weekly-sheet 里的 block 与 `training_package_payload` 里的 block 逐字段同形」**（同一个包、同一周，比对两边的 block dict）——**这条是两个投影不漂移的唯一守卫**。

## 0.2 其余 6 条（简报的预检总表里有完整实测依据）

- **P4-A2**：**`weekly_factors_of` 已经存在**（Plan 02 Task 8 交付），实测签名 `weekly_factors_of(session, prescription_id: int) -> list[WeeklyFactor]`，在 `prescription_stage.__all__` 里。`WeeklyFactor` 的 4 个字段 = `week:int / factor:float / reason:str / source:str`。**直接调用，不要重写。**
- **P4-A3**：**`OverrideRecord` 的 7 个字段全部无缺省**（`kind` / `target` / `old_value` / `new_value` / `reason` / `teacher_staff_no` / `applied_at`）。**请求模型必须是 5 字段的另一个 Pydantic 类**，`teacher_staff_no` 从身份头填、`applied_at` 从服务端时钟填（**让客户端传等于让它能冒充别的教师、还能伪造时间**）。`OverrideKind` 的 5 个值实测 = `weekly_frequency` / `substitute_exercise` / `intensity_step` / `volume_scale` / `pause`（**下划线不是连字符**）→ **值域直接引 `OverrideKind`，不要在 schema 里抄第二份字符串**。⚠️ **调 `apply_overrides` 必须传 `exercises=`**（实测签名 `apply_overrides(pkg, records, *, exercises)`，关键字必填）—— 否则 `SUBSTITUTE_EXERCISE` 会留下旧动作的视频 URL，那是 Plan 02 顶回 2 逐字说的「**一个看起来正常的谎**」。
- **P4-A4**：`prescription.teacher_overrides` 是 **`TEXT NOT NULL`** 的 `JsonText` → 「追加一条覆盖」= **读 JSON 列表 → append → 写回**，不是 INSERT；空列表写 `[]` 不写 `NULL`。**顺序承重**（Plan 02 的 5.4：多条覆盖同一目标由**列表顺序**决定、后者胜）→ **不要按 `applied_at` 重排序**。
- **P4-A5（对接缺口 1）**：实测 `openapi()["components"]` 里**没有 `securitySchemes`**、spec 顶层**没有 `security`**、47 个路径里**声明过的 header 参数为空**。**把 `X-Student-Id` / `X-Teacher-Staff-No` 注册成 OpenAPI 的 `apiKey` securityScheme**（`in: header`），需要它们的端点挂 `dependencies=[Security(...)]`。**不注册的后果：Swagger UI 上没有地方能填、生成的 TS 客户端也不知道要发** → 前端一接就撞 401 且不知道为什么。
- **P4-A6（对接缺口 3）**：实测 **23 个 detail 路径的 path 参数名 distinct = `['pk_value']`**。**给 `build_crud_router` 加 `pk_alias: str | None = None`**：`None` → 自动取**资源路径的单数 + 下划线**（`semesters`→`semester_id`、`course-sections`→`course_section_id`、`fitness-test-results`→`fitness_test_result_id`），显式传则覆盖。**纯 OpenAPI 层的改名，不动 DB、不动路由匹配。** ⚠️ **23 个 detail 路径的 URL 模板会变，Task 3 那条遍历型守卫测试要跟着改。**
- **P4-A7（对接缺口 2，本 Task 不修、只记录）**：CORS 是 `allow_origins=["*"]` 且**没有 `allow_credentials`**（浏览器规范禁止两者并存）。**Plan 04 的前端不得用 cookie / `fetch(..., {credentials:'include'})`**，身份只能走请求头。控制者已把这条写进计划的「计划边界说明」。

## 0.3 你要交付什么

**Create**：`backend/app/api/routers/prescription.py`、`backend/tests/api/test_prescription_api.py`
**Modify**：`backend/app/api/schemas/prescription.py`（**⚠️ 它由 Task 3 创建，本 Task 只补特例模型，不要覆盖**）、`backend/app/api/routers/__init__.py`（**⚠️ 新 router 挂这里，不是 `main.py`**——`main.py` 的注释逐字写着「只 include 这**一个**汇总路由：Task 5/7/8/9 各加一个 router 时改的是 `app/api/routers/__init__.py`，不是本文件（本文件压着 `pe.db` 禁区那条纪律）」）、**`backend/app/api/crud.py`（P4-A6：加 `pk_alias`）**、**`backend/app/api/deps.py`（P4-A5：securityScheme）**、**`backend/app/pipeline/prescription_stage.py`（P4-A1：提取 block 级投影）**、`backend/tests/api/test_crud.py`（P4-A6 的连带）

**四个端点**（简报的 Task 4 节有完整口径）：
- `GET /api/students/{student_id}/prescriptions/current`
- `GET /api/students/{student_id}/weekly-sheet?as_of=YYYY-MM-DD`
- `POST /api/prescriptions/{id}/overrides`
- `POST /api/prescriptions/{id}/regenerate`

**⚠️ 必须传导的 Plan 02 结论（简报的 Task 4 节逐条列了 6 条，这里点最容易漏的 3 条）**：
1. **`paused=True` 时 `sessions` 原样保留**（P8-A3）→ 前端靠 `paused` 字段决定渲染什么，**不要在后端把 `sessions` 清空**。「暂停」与「本周量为 0」是两件不同的事。
2. **`WeeklySheet` 刻意不提供跨单位的周总量汇总**（P8-A1）→ **API 也不要加**。`volume_unit` 值域 `{min, reps, unspecified}`，相加就是 Plan 02 Task 5 的 F1-1 那个「混合量纲 float」错误。**前端要显示总量就自己按单位分组显示。**
3. **`previous_had_overrides` 是「界面提示『该生上次存在人工覆盖』」的唯一载体**（P6-A2），**不是 `assembly_snapshot` 里的键**（往快照加键会让 Plan 02 钉死的「12 键 / +3 键」两条守卫变红）。**`POST .../regenerate` 的响应里要带这一列**，否则前端提示不出来。

## 0.4 执行强度（账本 Ruling 1 + Ruling 5）

**目标 0–1 轮 fix round。**
- **保留**：TDD 先红后绿；`app/domain/` 分支覆盖 **100%**（四格应逐字不变）；单一所有者；断言两侧不同源；架构守卫全绿；**既有 876 条测试一条都不许退步**。
- **不做变异**（Ruling 1：变异只在 Task 6 要求）。**但 Task 2 与 Task 3 的实现者都自己加了变异自证「新守卫有牙」，控制者两次都采纳并鼓励**——你若能廉价自证某条新守卫不是恒绿的，就做了并写进报告。
- **取消**：纯散文精度 → 记进「待清扫」清单。**但 Critical 级一律当场修。**
- ⚠️ **Ruling 5**：Plan 03 的独立评审席折进了控制者亲验，故**你的顶回是唯一的独立视角**。Plan 02 顶回 **25/25**，Plan 03 已顶回 **14/14**（累计 **39/39**）。共同点：**控制者对着「文档的形状」推理，实现者对着「守卫实际能抓到什么」推理。你在代码现场，你的判断优先。**
- ⚠️ **若你顶回 0 处，请在报告里显式写「0 处顶回」并说明你逐条核过哪些决定。**

## 0.5 纪律

- **禁区**：`backend/pe.db`（**不得存在**；`DEFAULT_DB_URL` 就指向它，手工起服务必须显式设 `PE_DB_URL`）、`backend/data/seed/`（0 文件）、`backend/data/**` **一个字节都不许动**（三个指纹 `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301`）。**不要跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`**。
- ⚠️ **控制者现在有一个 uvicorn 进程跑在 `127.0.0.1:8000`（用 `pe_demo.db`）**。你要手工起服务的话**换一个端口**，别撞。
- **PowerShell**：`;` 分隔；不支持 `&&`/`||`；没有 heredoc；反引号会被吃；`python -c` 里嵌双引号会被吃、**f-string 里不能有反斜杠** → 复杂逻辑写临时 `.py`。**所有写文件走 python。**
- **`git add` 按文件名逐个加**。commit 信息用 python 写 UTF-8 **无 BOM** 临时文件 + `git commit -F`。**不要 push。**
- **数列/字段/成员一律用运行时口径**，**绝不用正则数源码**（硬规矩 #89）；**数行尾/字节数用 `read_bytes()`**（#89 扩写）；**数「一个名字有几份定义」用 AST**（#89 再扩写）；**一个探针里若有两种口径能回答同一个问题，以运行时那一种为准、另一种标注为不可用**（硬规矩 #103）。
- **断言「A 等于/不等于 B」时，若任一侧经过序列化/编码/格式化，必须先证明那个变换是单射**（硬规矩 #99）。
- **不要凭记忆构造 HTTP 请求的 payload**：先从 `/openapi.json` 读那个 schema 的 `required`（硬规矩 #89 的同族；控制者本次冒烟的第一版脚本就栽在这里，见账本控制者错误 #13）。
- **报告与探针脚本一律用 python 写**，不要用编辑器工具反复改 `.superpowers/` 下的文件。

## 0.6 commit 与报告

**建议 3 个 commit**：① P4-A1 的投影提取 + P4-A6 的 `pk_alias` + P4-A5 的 securityScheme（三条都是「改既有代码」，先做完并让 876 条仍全绿）；② 四个特例端点 + 它们的测试；③ 收尾（全量 + 覆盖率 + 扫描面）。

报告写进 `c:\Users\whwenhao\Desktop\Physical_Education_ims\.superpowers\sdd\2026-10-08-实施计划03-反馈预警与CRUD-API层\task-4-report.md`（**python 写**）。至少 8 节：① 环境与基线复现；② **P4-A1 的提取**（新函数名、两处调用点、那条「逐字段同形」的测试名）；③ **P4-A5/A6 的落地证据**（`/openapi.json` 里 `securitySchemes` 的内容、23 个 detail 路径的参数名 distinct 从 `['pk_value']` 变成什么）；④ 四个端点的最终路径/方法/请求响应形状；⑤ Plan 02 传导的 6 条逐条落地位置；⑥ 待清扫 / 关切 / **没按派单做的地方（0 处也要写）** / **顶回控制者的地方（0 处也要显式写并说明核过哪些决定）**；⑦ 最终验收（passed 数 876 → ?、覆盖率四格应不变、表数 25、扫描面 49 → ?、端点数 47 → ?、三个指纹、`git diff <base> HEAD -- backend/data` 为空、`pe.db` 不存在）；⑧ commit sha。

## 0.7 交回控制者

最终回复里给出（**简洁，不要贴大段代码**）：commit sha 与说明 / passed 数 / 覆盖率四格（应逐字不变）/ 扫描面与端点数的新值 / **P4-A1 提取出的函数名与那条同形测试的名字** / **`securitySchemes` 的最终内容** / **23 个 detail 路径参数名的新 distinct** / 四个端点的路径与方法 / Plan 02 传导的 6 条是否全部落地 / 三个指纹 / 顶回控制者的地方 / 没按派单做的地方 / 待清扫条数 / 报告字节数与行数。

---

