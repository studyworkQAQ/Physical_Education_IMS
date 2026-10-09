# Plan 03 Task 4 结案报告 —— 处方侧的特例端点（教师覆盖 + 本周训练单 + 手动重生成）

**分支** `feature/plan-03-feedback-alert-crud-api`　**基线** `9062b37`　**目标** 0–1 轮 fix round
**结论**：三个 commit 落地，**910 passed**（876 → 910），`app/domain` 覆盖率四格**逐字不变**，
扫描面 49 → **50**，`/api/` 路径模板 47 → **51**，三个指纹逐字不变，`backend/data` 的 diff 为空，
`pe.db` 仍不存在。**顶回控制者 3 处**、**没按派单做的地方 4 处**（逐条见第 ⑥ 节），待清扫 **5** 条。

---

## ① 环境与基线复现

**开工第一件事（硬规矩 #73）的 import 冒烟**：

```
cd backend
python -c "import sqlalchemy, fastapi, uvicorn, httpx, pydantic, yaml; print(sqlalchemy.__version__, fastapi.__version__)"
→ 2.1.3 0.141.1
```

六个包全部导入成功、退出码 0，**没有撞上 `ImportError: DLL load failed`**（Smart App Control 没拦
`.pyd`），故按派单继续，没有停手交回。环境：Python 3.11.1（无 venv）、SQLAlchemy **2.1.3**、
FastAPI **0.141.1**、Starlette 1.7.0、Pydantic 2.13.5、uvicorn 0.54.0、httpx 0.28.1。

**基线复现**（开工时在工作树干净的 `9062b37` 上亲跑）：

| 项 | 派单给的值 | 我复跑的值 |
|---|---|---|
| `python -m pytest -q` | 876 passed | **876 passed**（94.84 s） |
| 分支 / 基线 commit / 工作树 | `feature/plan-03-…` / `9062b37` / 干净 | 逐字相符 |
| `backend/pe.db` | 不得存在 | **不存在** |
| `backend/data/seed/` | 0 文件 | **0 文件** |

⚠️ **控制者那个跑在 `127.0.0.1:8000` 的 uvicorn 我没有碰**，也**没有另起服务**：
四个端点的取证全部走 `TestClient`（进程内 ASGI，不开端口）+ `app.openapi()` 实读，
于是「撞端口」与「`pe.db` 被建出来」两个风险都不存在。

---

## ② P4-A1（Critical）的落地：block 级投影的提取

**新函数**（全部住在 `backend/app/pipeline/prescription_stage.py`）：

| 函数 | 公开性 | 职责 |
|---|---|---|
| **`_block_payload(block) -> dict`** | 私有 | **一个 `AssembledBlock` → 可 JSON 的 dict（10 个键）**。P4-A1 要的那个提取 |
| `_session_payload(session) -> dict` | 私有 | 一课（`day` / `focus` / `blocks`），逐个 block 经 `_block_payload` |
| `weekly_sheet_payload(sheet) -> dict` | **公开**（进 `__all__`） | `WeeklySheet` → 6 键 JSON，`sessions` 逐个经 `_session_payload` |

**两处调用点**（这就是「提取」而不是「复制」的证据）：

1. `training_package_payload(pkg)` —— 教师端 / 落库那一侧。原本内嵌的三层字典推导
   现在只剩最外层三格 + `weeks`，课与 block 两级一律走上面两个函数。
2. `weekly_sheet_payload(sheet)` —— 学生端「本周训练单」那一侧。

⚠️ **我比派单多提了一层**：派单只点了 block 级（`_block_payload`），而课级那三行
（`{"day", "focus", "blocks"}`）若留在两处各写一遍，就仍然是两个所有者。故一并提成
`_session_payload`。

**「逐字段同形」那条守卫的名字**（派单点名要的、两个投影不漂移的唯一守卫）：

```
tests/api/test_prescription_api.py::
    test_the_weekly_sheet_blocks_are_field_for_field_the_training_package_ones
```

⚠️ 它**走 HTTP、两侧是两条真的代码路径**：学生侧
`GET /api/students/{id}/weekly-sheet`（`WeeklySheetRead` → `AssembledSessionRead` →
`AssembledBlockRead`），教师侧 `GET /api/prescriptions/{id}` 的 `training_package`
（`PrescriptionRead.training_package: dict`，**没有**嵌套模型，故是投影的原样输出）。
于是它能抓到「`response_model` 把投影多产出的字段静默过滤掉了」那一类失效——
而那正是给了 `response_model` 之后新出现的风险（见第 ⑥ 节关切 1）。

**P4-A1 那份实测证据我也复现了一遍**（`test_the_block_projection_is_json_serialisable_without_asdict`）：
`json.dumps(dataclasses.asdict(sheet))` 抛 `TypeError: cannot pickle 'mappingproxy' object`，
**加上 `default=str` 抛的是同一个错**（`asdict` 在到达 `json` 之前就死了）；
而 `weekly_sheet_payload` 与 `training_package_payload` 的输出 `dumps → loads` 逐字相等。
⚠️ 那条测试先断言「这个包里确实有 `mappingproxy`」（`RED-END-ABN-01` 第 1 周
`hr_zone` 非 `None` 的 block 有 16 个），否则它会因为「压根没有只读映射」而假绿。

**连带交付：反向映射**（派单没列，但缺了它四个端点里的两个跑不起来，见第 ⑥ 节顶回 2）：

| 函数 | 职责 |
|---|---|
| `training_package_from(payload, snapshot) -> TrainingPackage` | 两个 JSON 列 → domain 对象（`hr_zone` list→tuple、`impact_level` str→枚举、`structure` dict） |
| `override_record_payload(record) -> dict` | `OverrideRecord` → JSON 列表的一项（`kind` 写 `.value`、`applied_at` 写 `.isoformat()`） |
| `override_records_of(payloads) -> list[OverrideRecord]` | 反向；**一个都不重排**（P4-A4） |
| `effective_package(row, *, exercises, extra=())` | 骨架 × 覆盖 = **当前实际生效**的包 |
| `_prescription_values(...) -> dict` | 处方行那 **16** 个列值的唯一所有者（批处理与单人生成共用） |
| `_replace_previous(previous, as_of)` | 上一张置 `replaced`（同上） |
| `regenerate_for_student(...) -> Prescription` | 单人重生成（触发 5） |

守卫：`test_training_package_from_is_the_exact_inverse_of_the_payload`（经一次真的 JSON 往返后
`weeks == pkg.weeks`、再投影一次是不动点、快照键集与 `hrmax` 原样）、
`test_an_override_record_survives_the_json_column_and_keeps_its_order`（7 键逐字 + 往返相等 +
**时刻刻意递减**的四条记录读回来仍是原序）。

---

## ③ P4-A5 / P4-A6 的落地证据（全部从 `/openapi.json` 实读）

### P4-A5：`components.securitySchemes` 的最终内容

**改前**：`openapi()["components"]` 里没有 `securitySchemes`、spec 顶层没有 `security`、
47 个路径里声明过的 header 参数为空（控制者实测）。
**改后**（`app.openapi()` 实读，逐字）：

```json
{
  "X-Student-Id": {
    "type": "apiKey",
    "in": "header",
    "name": "X-Student-Id",
    "description": "学生身份（学号代理键 student.id 的整数字面量）。⚠️ 原型口径：没有签名、没有过期、没有吊销，上线前必须换成真实会话。缺头 → 401 unauthenticated；头存在但不是整数 → 422 request_validation_failed；与目标数据的所有者不符 → 403 forbidden。"
  },
  "X-Teacher-Staff-No": {
    "type": "apiKey",
    "in": "header",
    "name": "X-Teacher-Staff-No",
    "description": "教师身份（工号 teacher.staff_no 的字面量）。⚠️ 原型口径同上。缺头或全空白 → 401 unauthenticated；工号不在 teacher 表里 → 403 forbidden（require_teacher：一条覆盖记录的 teacher_staff_no 是研究数据，写进一个不存在的工号等于让它作废）。"
  }
}
```

* spec **顶层** `security` = `None`（刻意不设全局要求：那会把 `/api/health` 一起圈进去）。
* 挂了 `security` 的操作**恰好四个**（23 个 CRUD 资源一个都没有，故前端不会以为每个 CRUD 都要登录）：

| 操作 | `security` |
|---|---|
| `POST /api/prescriptions/{prescription_id}/overrides` | `X-Teacher-Staff-No` |
| `POST /api/prescriptions/{prescription_id}/regenerate` | `X-Teacher-Staff-No` |
| `GET /api/students/{student_id}/prescriptions/current` | `X-Student-Id` |
| `GET /api/students/{student_id}/weekly-sheet` | `X-Student-Id` |

⚠️ **`auto_error=False` 是承重的**：`APIKeyHeader` 缺省会在缺头时自己抛 `HTTPException(403)`，
而本仓「缺身份」的既有口径是 `current_student` / `current_teacher` 抛的 **401**
（`tests/api/test_scope.py::test_missing_identity_header_is_401` 钉着）。
故这两个 scheme **只负责声明**（进 OpenAPI），判定仍在那两个依赖上——
于是 Swagger UI 上填得进去、TS 客户端知道要发，而码一个都没变。

守卫：`test_the_identity_headers_are_registered_as_openapi_security_schemes`（四拍：
两格的内容 / 四个端点各指对的那一格 / **73 个 CRUD 操作一个都不带 `security`** / 顶层为 `None`）。

### P4-A6：23 个 detail 路径参数名的新 distinct

**改前** distinct = `['pk_value']`（`/api/semesters/{pk_value}`）。
**改后**（从 `openapi()["paths"]` 实读，**23** 个 detail 路径、distinct **23** 个）：

`alert_id`、`body_composition_id`、`class_session_id`、`course_section_id`、`derived_metric_id`、`enrollment_id`、`exercise_id`、`fitness_test_batch_id`、`fitness_test_result_id`、`interest_survey_id`、`mini_test_id`、`notification_id`、`percentile_snapshot_id`、`prescription_id`、`prescription_template_id`、`rpe_record_id`、`semester_id`、`stratification_result_id`、`student_id`、`teacher_id`、`training_log_id`、`weekly_adjustment_id`、`weekly_class_report_id`

⚠️ `pk_value` **一个都不剩**（守卫里有一拍逐字断言
`not [key for key in paths if key.endswith("/{pk_value}")]`）。

**实现口径**：`build_crud_router` 加 `pk_alias: str | None = None`，`None` → `_pk_alias_of(path)`
（去掉末尾一个 `s` + 连字符换下划线 + `_id`）。⚠️ **纯 OpenAPI 层**：端点函数的形参
**仍叫 `pk_value`**，靠 `Path(alias=alias)` 绑到 URL 模板上（本机 FastAPI 0.141.1 亲跑验证），
故不动 DB、不动路由匹配，也不必给 23 个函数各改一次形参名。
⚠️ `update_row` 的形参**换了序**（`payload` 提到 `pk_value` 前面）：`Path(alias=…)` 是缺省值，
而 Python 不允许带缺省的形参排在不带缺省的前面；FastAPI 按名字与标注解析、不看顺序，
故对请求形状零影响（`create_row` 的 `payload` 本来就排第一）。

**连带改的 Task 3 守卫**（派单点名的那条）：
`tests/api/test_crud.py::test_the_scope_hook_rejects_a_mismatched_identity_with_403` 里那两把
`/api/probe-training-logs/{pk_value}` 与 `/api/training-logs/{pk_value}` 换成
`…/{probe_training_log_id}` 与 `…/{training_log_id}`；另加三条新守卫：
`test_every_detail_path_names_its_pk_after_the_resource`（遍历型，期望侧是 23 个字面量）、
`test_the_automatic_pk_alias_is_the_singular_resource_name_plus_id`、
`test_an_explicit_pk_alias_overrides_the_automatic_one`。
工厂的配置校验从五道变**六道**（`pk_alias` 必须是标识符），
`test_the_factory_rejects_a_bad_configuration` 跟着加了一格。

### P4-A7（本 Task 不修、只记录）

CORS 仍是 `allow_origins=["*"]` 且没有 `allow_credentials`（浏览器规范禁止两者并存）。
**一个字节都没动**，`main.py` 也没动。⚠️ 传导给 Plan 04 的约束（前端不得用 cookie /
`fetch(..., {credentials:'include'})`，身份只能走请求头）已随 P4-A5 写进
`app/api/deps.py` 那两个 scheme 的 `description`——于是它会**出现在 `/openapi.json` 里**，
前端读 spec 时就能看到，而不只躺在计划文档里。

---

## ④ 四个端点的最终路径 / 方法 / 请求响应形状

| # | 方法与路径 | 身份 | 请求 | 200 响应 | 错误 |
|---|---|---|---|---|---|
| 1 | `GET /api/students/{student_id}/prescriptions/current` | `X-Student-Id` + `require_scope` | `?as_of=YYYY-MM-DD`（可省） | `PrescriptionRead`（**16 列**，含 5 个 `JsonText` 列） | **404** `no_active_prescription`／401／403 |
| 2 | `GET /api/students/{student_id}/weekly-sheet` | 同上 | `?as_of=YYYY-MM-DD`（可省） | `WeeklySheetRead` = `{week:int, factor:float, reasons:[str], sources:[str], paused:bool, sessions:[{day,focus,blocks:[10 键]}]}` | **404** `no_active_prescription` **或** `outside_microcycle`／401／403 |
| 3 | `POST /api/prescriptions/{prescription_id}/overrides` | `X-Teacher-Staff-No` + `require_teacher` | `OverrideCreate` = **5 字段** `{kind, target?, old_value, new_value, reason}`（`required` 实读 = 4 个，`target` 可省） | **200** `OverrideResultRead` = `{prescription_id, overrides:[7 键…], training_package:{4 键}}` | **422**（domain 的五档 + `reason` 空）／404／401／403 |
| 4 | `POST /api/prescriptions/{prescription_id}/regenerate` | 同上 | `?as_of=YYYY-MM-DD`（可省），**无请求体** | **200** `PrescriptionRead`（含 `previous_had_overrides`） | **422**（Z0 / 匹配不上 / 无触发）／404／401／403 |

⚠️ **两个 POST 都回 200、都不带 `Location`**，与 Task 3 那 23 个资源的 `POST → 201 + Location`
**刻意不同**：那条约定说的是「创建了一个新资源」，而这两个是「对已存在的资源做一次操作」，
**没有新的 URI 可指**（教师覆盖记录是 `prescription` 的一个 JSON 列，没有自己的表）。
编一个 `…/overrides/0` 出来会让前端以为覆盖记录可以单独 GET/PATCH。

⚠️ **两个 404 的 `code` 不同**（端点 2）：`no_active_prescription` = 你压根没有处方；
`outside_microcycle` = 你有处方、但问的那一天不在它的 4 周里。合成一个码的话前端无从区分，
而两者的正确 UI 完全不同。⚠️ 实现上用 `app.api.errors.error_response(...)` 直接造响应，
不是 `raise HTTPException(404)`——后者的 `code` 会被 `_CODE_BY_STATUS` 折成通用的 `not_found`。

**`as_of` 的口径**：查询参数传，缺省取服务端当天（`_business_day` 是「今天是什么日子」
在本模块的唯一住址）。⚠️ 计划那条决定还提了一个 `PE_AS_OF` 环境变量口子，
**我没有实现**（理由见第 ⑥ 节偏离 3）。测试**一律显式传** `as_of`，
缺省那一档只由 `test_as_of_defaults_to_the_server_clock` 一条看着。

**31 条新测试**（`tests/api/test_prescription_api.py`，分三批：A 投影层 / B 端点行为 / C 对接面）。
计划 Step 1 点名的 10 条**全部落地**，逐条对照：

| 计划点名 | 落地 |
|---|---|
| `test_current_prescription_is_404_when_there_is_none` | ✅ 同名 |
| `test_weekly_sheet_carries_volume_unit_per_block` | ✅ 同名 |
| `test_weekly_sheet_reports_paused_and_keeps_the_sessions` | ✅ 同名 |
| `test_the_sheet_has_no_cross_unit_total_field` | ✅ 同名（按**键集相等** + 递归断言任何一层都不出现 `total`） |
| `test_an_unspecified_addon_block_comes_back_with_zero_volume` | ✅ 同名（两拍：骨架 0.0 + 叠一个 0.5 系数后仍 0.0） |
| `test_an_empty_override_reason_is_422_with_the_domain_message` | ✅ 同名（含「库里一个字没写」那一拍） |
| `test_overrides_append_and_the_list_order_decides` | ✅ 同名（四拍） |
| `test_regenerate_clears_overrides_and_sets_previous_had_overrides` | ✅ 同名（五拍） |
| `test_regenerating_twice_on_the_same_day_returns_200_and_one_row` | ✅ 同名 |
| `test_a_student_cannot_read_another_students_weekly_sheet` | ✅ 同名（五拍：双向 403 + 自己 200 + 缺头 401 + `current` 也挂了闸门） |

---

## ⑤ Plan 02 传导的六条：逐条落地位置

| # | 结论 | 是/否 | 落地位置（生产代码 → 守卫） |
|---|---|---|---|
| 1 | **`paused=True` 时 `sessions` 原样保留**（P8-A3） | **是** | `weekly_sheet_payload` 只抄 `sheet.sessions`、一个 block 都不删；`weekly_sheet` 端点走 `effective_package`（**覆盖之后**的包，否则 `paused` 永远 `False`）→ `test_weekly_sheet_reports_paused_and_keeps_the_sessions`（三拍，第三拍是 `after["sessions"] == before["sessions"]`，并附一拍「库里那一列的 `paused` 仍是 `False`」） |
| 2 | **不提供跨单位的周总量汇总**（P8-A1） | **是** | `WeeklySheetRead` 6 个字段、唯一的 `float` 是 `factor`；`weekly_sheet_payload` 一个汇总键都不加 → `test_the_sheet_has_no_cross_unit_total_field`（键集相等 + 递归「任何一层都不出现 `total`」+ 顶层 float 恰好只有 `/factor`） |
| 3 | **`unspecified` 的 block `weekly_volume` 恒 `0.0`**（P5-A3） | **是** | 端点原样返回，`structure` 是空 dict、`intensity_text` 是那句「附加模块…」→ `test_an_unspecified_addon_block_comes_back_with_zero_volume`（两拍；⚠️ 夹具必须走 `apply_safety`，addon 是**它**追加的，只 `assemble` 的话每课只有 2 个 block、这一档压根不出现） |
| 4 | **`reason` 非空由 domain 判、API 不再校验一遍** | **是** | `OverrideCreate.reason` 是裸 `str`，**没有** `min_length` / 校验器；端点里 `OverrideRecord(...)` 的构造排在任何写入之前 → `test_an_empty_override_reason_is_422_with_the_domain_message`（`code == "unprocessable_value"` 而不是 `request_validation_failed`，消息原文含「一条没有理由的覆盖对研究毫无价值」） |
| 5 | **`old_value` / `new_value` 一律 `str`** | **是** | `OverrideCreate` 与 `OverrideRecordRead` 两处都是 `str`，没有联合类型 → `test_the_block_schema_covers_exactly_the_projection_keys` 钉字段集，`/openapi.json` 里 `OverrideCreate.properties` 实读为 `{"type": "string"}` |
| 6 | **覆盖不继承，`previous_had_overrides` 是唯一载体**（P6-A2） | **是** | `_prescription_values` 写 `"teacher_overrides": []` 与 `"previous_had_overrides": bool(previous is not None and previous.teacher_overrides)`；`regenerate` 的 `response_model` 是 `PrescriptionRead`（16 列全给），故那一列自然在响应里 → `test_regenerate_clears_overrides_and_sets_previous_had_overrides`（五拍，含「旧那张被置 `replaced` 而 `valid_to` 一个字没改」）。⚠️ **`assembly_snapshot` 一个键都没加**：那条测试顺带断言 `len(body["assembly_snapshot"]) == 15`，于是 Plan 02 钉死的「12 键 / +3 键」两条守卫不会因为本 Task 变红 |

⚠️ 另外两条**没在派单六条里、但同族**的传导也落地了：
**P4-A2**（`weekly_factors_of` 已存在 → 直接调用、没重写；端点 2 就是它的**第一个生产调用方**，
Plan 02 的 docstring 逐字写着「本函数是给 Plan 03 的 API 层准备的」）与
**P8-A4**（顺序由 `ORDER BY created_at, id` 定，API 侧一个都不重排）。
守卫是 `test_the_weekly_sheet_multiplies_every_adjustment_of_that_week`
（`factor == 0.7200000000000001` 逐字——**裸乘积不 round**；`reasons` / `sources` 两条都在且按 DB 序；
`weekly_volume == 27.6`；**第 2 周的调整不进第 1 周的账**）。

---

## ⑥ 待清扫 / 关切 / 没按派单做的地方 / 顶回控制者的地方

### 顶回控制者（**3 处**）

**顶回 1 —— P4-A6 的自动推导认不出 `-es` 复数，`fitness-test-batches` 会推成 `fitness_test_batche_id`。**
派单给的规则是「资源路径的单数 + 下划线」并举了三个例子（`semesters` / `course-sections` /
`fitness-test-results`），**三个都不是 `-es` 结尾**。我照规则实现后跑遍历守卫，
23 个名字里有一个对不上：`fitness-test-batches` → `fitness_test_batche_id`（多一个 `e`）。
处置有两条路：① 把推导改聪明（认 `ches` / `shes` / `xes` / `zes`）；② 让那一行显式传 `pk_alias`。
**我选 ②**，理由：英语复数还原是有例外的词法问题——`batches` 去 `es`、而 `exercises` 只去 `s`，
**两者都以 `ses` 结尾**，故任何后缀表都必然不完备（`classes` → `classe`），
而为一个 URL 命名问题引入第二份词表违反 Global Constraint #3。
② 的额外收益是：**「显式覆盖」那一档从此有了生产调用方**，不再是死代码（硬规矩 #39）。
守卫：`test_the_automatic_pk_alias_is_the_singular_resource_name_plus_id` 把「推导给出
`fitness_test_batche_id`」这件事**字面钉住**（谁把推导改聪明，这条会红，而那是一次
需要被看见的改动），并断言 23 行里显式传 `pk_alias` 的**恰好那一行**。

**顶回 2 —— 派单的 Files 清单缺了一样东西：JSON → `TrainingPackage` 的反向映射，没有它端点 2 与 3 跑不起来。**
派单说端点 2 要「调 `weekly_factors_of` + `weekly.weekly_training_sheet`」、端点 3 要「调
`apply_overrides`」，而**这三个函数只吃 domain 的 dataclass**；API 手上有的只是
`prescription.training_package` / `assembly_snapshot` / `teacher_overrides` 三个 **JSON 列**。
Plan 02 结案时逐字写下了这件事：`tests/pipeline/test_prescription_stage.py` 的
`test_db_rows_reach_the_read_model_with_their_order_intact` 里那段注释——
「JSON → `TrainingPackage` 的反向映射今天**不存在**（那是 Plan 03 的 API 层的活），
而本 Task 不该顺手造一个」。故它不是可选项。
⚠️ **而它的住址我选了 pipeline 层、不是 `app/api/`**（与那句注释的字面不同，理由两条）：
① 它是 `training_package_payload` 的**反面**，两个函数必须逐格对齐
（`hr_zone` 的 tuple↔list、`impact_level` 的枚举↔`.value`、`structure` 的 mappingproxy↔dict），
把反面放到另一层就没人能一眼看出它们漂了；② Plan 03 的 Task 7（预警落地）与 Task 8
（大屏 / 学生端首页）都要读同一列，住在 router 里会逼它们 import 一个 router。

**顶回 3 —— `regenerate` 的实现体我放进了 `prescription_stage.regenerate_for_student`，并把处方行那 16 个列值提进 `_prescription_values` 与批处理共用。**
派单的 Files 只让我改 `prescription_stage.py` 的 P4-A1 那一条。但「手动重生成」要产出的是
**与批处理同一种行**（16 列、`teacher_overrides=[]`、`previous_had_overrides`、上一张置
`replaced`），而在 router 里重抄一遍那 16 个键就是第二个所有者——
`repo.upsert` 的更新分支是 **PATCH 语义**，漏改的那一处会**静默沿用旧值**
（那个函数的 docstring 逐字警告过这件事）。故我把它提成共用，
`generate_prescriptions` 现在也调 `_prescription_values` / `_replace_previous`。
⚠️ 这是本 Task 对已结案代码动得最深的一刀，故它有一条**端到端**的回归证据：
Plan 02 的 `tests/pipeline/test_prescription_stage.py`（含 500 人整学期回放）**一条都没改、全绿**。

### 没按派单做的地方（**4 处**）

**偏离 1 —— 加了 `app/api/deps.require_teacher`（派单没要求）。**
`current_teacher` 只判「有没有带头、是不是空白」，于是一个 `X-Teacher-Staff-No: WHATEVER`
会被放行，而那个串随后被写进 `teacher_overrides` 的 `teacher_staff_no` 一格。
spec §7.5 末段把那些记录当**研究数据**，一条挂在不存在的人身上的覆盖在事后**无从归属**。
这与 `require_scope` 第二支的理由**逐字同构**（那段 docstring 自己写着
「这一支是 `session` 参数存在的**全部理由**」）。故我补了对称的教师侧闸门：不在册 → **403**。
守卫 `test_the_teacher_side_rejects_an_unknown_or_missing_staff_no`（四拍：缺头 401 /
不在册 403 / 空白 401 / **在册 200** 的绿档，外加「403 那一档一个字都没写进库」）。
⚠️ **代价**：演示库若没有 `teacher` 行，教师侧端点会一律 403——
但那与 `require_scope` 对学生侧的既有行为**完全对称**（空库上学生侧本来就一律 403），
不是本 Task 新引入的门槛。

**偏离 2 —— commit 只有 3 个，但**内容**与派单建议的切分不同。**
派单建议 ①「三条改既有代码」②「四个端点 + 测试」③「收尾」。
实际是 ①`crud.py`+`deps.py`+`catalog.py`+`prescription_stage.py`+`test_crud.py`
②`schemas/prescription.py`+`routers/prescription.py`+`routers/__init__.py`+`test_prescription_api.py`
③本报告。⚠️ 原因：`git add -p` 是交互式的（派单的纪律禁止交互命令），
故**一个文件只能整体进一个 commit**；而 `prescription_stage.py` 同时装着
「P4-A1 的提取」与「反向映射 + `regenerate_for_student`」两批新增，无法按派单的切分拆开。
⚠️ 代价如实记录：commit ① 里 `weekly_sheet_payload` / `training_package_from` /
`effective_package` / `regenerate_for_student` **在它那一个 commit 上还没有生产调用方**
（调用方在 commit ②），它们的守卫也在 commit ②。两个 commit 相隔几分钟、且都在本 Task 内，
最终树是完整的。

**偏离 3 —— 没实现 `PE_AS_OF` 那个环境变量口子。**
派单的「决定」写的是「`conftest.py` 提供一个 `as_of` 覆盖（环境变量 `PE_AS_OF`），
测试一律显式传」——**两半是替代关系**，我做了强的那一半（测试一律显式传，
31 条里只有 `test_as_of_defaults_to_the_server_clock` 一条依赖真实时钟，且它在 docstring 里
交代了「跨过午夜跑会红」这个已知窗口）。不做环境变量那一半的理由两条：
① 它是「今天是什么日子」的**第二个所有者**（`_business_day` 已经是一个）；
② 它多一档「值不是合法 ISO 日期」的分支要守，而那一档在测试一律显式传的前提下**没有消费者**。

**偏离 4 —— 动了 `tests/api/test_crud.py` 之外的一个既有测试文件？没有。**
派单的 Modify 清单列了 `tests/api/test_crud.py`（P4-A6 的连带），我改了它；
但**没有**改 `tests/pipeline/test_prescription_stage.py`——我在
`training_package_from` / `override_record_payload` 的 docstring 里引用了两个测试名
（`test_training_package_from_is_the_exact_inverse_of_the_payload` 与
`test_an_override_record_survives_the_json_column`），⚠️ **这两条实际住在
`tests/api/test_prescription_api.py`**，且后者的真名多一个后缀
（`…_and_keeps_its_order`）。这两处引用**指向了错误的文件与名字**，属散文精度问题，
按账本 Ruling 1「纯散文精度 → 记进待清扫」处理（**待清扫 1**）。

### 关切（**4** 条）

**关切 1（最高）—— `response_model` 让 block 的形状有了第二个住址，而漂移是静默的。**
`AssembledBlockRead` 的 10 个字段与 `_block_payload` 的 10 个键是**两份**。
给 `response_model` 的理由是 P4-A5/A6 那一条立意（前端要能照 spec 对接，
不给的话 `/openapi.json` 里那一格的响应 schema 是空的）；代价是
**`response_model` 会过滤掉模型上没有的键**，故投影多产出一个字段时它在 HTTP 响应里
静默消失。拦它的守卫有两条、两侧不同源：
`test_the_block_schema_covers_exactly_the_projection_keys`（类 ↔ 函数输出）与
`test_the_weekly_sheet_blocks_are_field_for_field_the_training_package_ones`（两条 HTTP 路径互比）。
⚠️ 但**它们守不住「两侧同时改」**：谁往 `_block_payload` 加一个键、又往
`AssembledBlockRead` 加同一个键，两条守卫都绿——而那其实是**正确**的改动，故这一格是
「有意的许可」，不是漏洞。

**关切 2 —— `needs_review` 的处方被当成 current 返回给学生端，这与 Plan 02 的一句话有张力。**
`active_or_needs_review` 的 docstring 逐字写着「一张待人工复核的处方**不能被学生端当成
生效处方执行**」，而派单的 Interfaces 逐字写的是 `status ∈ {active, needs_review}`。
我按派单落地（返回它 + **带上 `status`**），并把判断留给前端。
⚠️ **传导给 Plan 04**：学生端在 `status == "needs_review"` 时**必须**挂一条横幅
（「本训练单待教师复核」），否则 spec §7.4 那句「宁可不自动，也不要自动错」在 UI 上落空。
反过来做（回 404）更糟：学生会看到「你没有训练单」，而他其实有一张待复核的，
那看起来像数据丢了。守卫 `test_a_needs_review_prescription_is_still_the_current_one_and_says_so`。

**关切 3 —— `require_teacher` 不判「这个教师能不能改这个学生的处方」。**
原型没有「教师 ↔ 班级 ↔ 学生」的授权模型（`course_section.teacher_id` + `enrollment`
能推出一个），故今天**任何在册教师可以覆盖任何学生的处方**。
这与 `require_scope` 对学生侧的严格程度**不对称**，如实记录。
收窄它是 Plan 04 教师端要不要做的决定，不是本 Task 的。

**关切 4 —— 手工重生成出来的处方行会被重放删掉。**
`regenerate_for_student` 的 `batch_id` 取被点那一行自己的（口径与
`WeeklyAdjustment.batch_id` 那一段逐字相同：教师手工发起的写入没有自己的批次），
而 `daily._replay_cleanup` 按 `batch_id` 整批删 —— 于是**重放那一天会连带删掉
教师这次手工重生成的行**。这是 Plan 02 Task 7 已经登记过的同一条代价的第三个面
（前两个是「重放会丢掉教师覆盖」与「重放会删掉教师当天的手工微调」）。
本仓不做迁移、也没有「人工数据豁免于重放」的机制，故不擅自加一个。

### 待清扫（**5** 条）

1. `prescription_stage.py` 里 `training_package_from` / `override_record_payload` 的 docstring
   引用了两个测试名，指向的文件与名字都不对（见偏离 4）。**纯散文**。
2. `app/api/routers/prescription.py` 的模块 docstring 说「本模块的两个 GET 刻意不接受
   `X-Teacher-Staff-No`」，而教师端要看某个学生的训练单这件事**今天没有任何端点能做**
   （Task 8 的大屏是聚合读，不是单人训练单）。⚠️ 这是**能力缺口**不是散文：
   Plan 04 的教师端若要「点开一个学生看他的本周训练单」，需要 Task 8 补一个
   教师身份的变体。**记在这里以免下一个人以为它已经存在。**
3. `crud.py` 模块 docstring 那张 23 行对照表的表头仍是「路径 / 表 / 字段名的形状」，
   **没有 `pk_alias` 那一列**；而「URL 模板长什么样」现在要多读一个 `_pk_alias_of`。
   加一列会让那张表变宽到难读，故本 Task 没加（纯散文精度）。
4. `deps.py` 的 `require_scope` docstring 里那句「教师不走这道闸门……由 `current_teacher`
   与 Task 8 的教师路由各自负责」现在**过期了一半**：教师侧的在册闸门已经有了
   （`require_teacher`，本 Task），而它住在同一个文件里。
5. `tests/api/test_prescription_api.py` 的 `_seed` 用手工构造的 **7 键**最小快照
   （生产是 28 键）。⚠️ 若将来 `_profile_of` 或 `match_template` 开始读第 8 个键，
   本文件的夹具会 `KeyError` —— 那是**响的**，但响在测试里而不是在生产里，
   故记一条：加键时要同步这里。

### 变异自证（Ruling 1 说本 Task 不做变异，但 Task 2/3 的实现者都自己加了、控制者两次都采纳）

10 个变异，逐个「按字节备份 → 改 → 跑指定测试 → 按字节还原」，**10/10 RED、0 恒绿、0 SKIP**，
且跑完四个文件**逐字节还原**（脚本末尾自己核了一遍）。⚠️ 锚点里的 `\n` 要按目标文件的
实际行尾改写：实测本仓工作树是**混合**的（`prescription_stage.py` / `deps.py` / `main.py`
是 CRLF，`crud.py` / `schemas/prescription.py` / 本 Task 新建的两个文件是 LF；索引里一律 LF），
第一版脚本因此在 CRLF 文件上命中 0 次、静默 SKIP 掉一个变异。

| # | 变异 | 结果 |
|---|---|---|
| M1 | `AssembledBlockRead` 删掉 `volume_unit`（两个投影漂移） | **RED**（2 failed） |
| M2 | `override_records_of` 按 `applied_at` 排一次序（P4-A4 禁止的那件事） | **RED** |
| M3 | `_prescription_values` 让重生成**继承**覆盖（spec §7.5 明令禁止） | **RED** |
| M3b | `previous_had_overrides` 恒 `False`（P6-A2 的唯一载体失效） | **RED** |
| M4 | 覆盖端点改成「先写、后算」 | **RED**（1 failed, 1 passed） |
| M5 | `read_one` 去掉 `Path(alias=…)`（P4-A6 失效） | **RED** |
| M6 | 学生侧 GET 去掉 `Security(…)`（P4-A5 失效） | **RED** |
| M7 | `_current_prescription` 去掉 `valid_from <= as_of` | **RED** |
| M8 | `WeeklySheetRead` 多一个 `total_volume`（P8-A1 禁止的那件事） | **RED** |
| M9 | `effective_package` 不叠覆盖了 | **RED**（2 failed） |

⚠️ **变异自证抓到一处我自己写错的因果陈述**（第 1 版里 M3 是「`_replace_previous` 的
`<` 改成 `<=`」，结果**恒绿**）。查清了原因：`_prescription_values` **也**写 `status`，
而 `repo.upsert` 的更新分支会把那 16 个键逐个 `setattr` 上去，
于是「同一天重生成时先置 `replaced`、随后被写回 `active`」两步互相抵消 —— **不可观测**。
处置：不改实现（严格小于逐字等于 Plan 02 已结案的那一行，且「不要动正要被 upsert 的那一行」
这条意图值得留着），但把 `_replace_previous` 的 docstring 与
`test_regenerating_twice_on_the_same_day_returns_200_and_one_row` 的 docstring
**都改成如实的**（「这一拍是**过度确定**的：两条机制各能单独保住它，故它对任一条的变异都无感；
它钉的是可观测行为，不是某一条实现」）。⚠️ 这正是 Ruling 5 说的那件事的一个实例：
对着文档的形状推理会写下「严格小于是承重的」，对着守卫实际能抓到什么推理才知道它不是。

### 一条**性能**上的如实交代

`tests/pipeline/test_backfill.py::test_backfill_500_students_under_60_seconds` 在
**全量跑**时红了两次（`elapsed` = 62.72 s / 61.58 s，阈值 60 s），
单独跑与基线对照都绿。取证（**不是我的回归**）：

| 口径 | 基线 `9062b37`（`git worktree` 到 TEMP，不动我的工作树） | 本 Task 的树 |
|---|---|---|
| 单独跑那一条的 **setup** 时长 | **57.21 s** | **57.39 s**（+0.3 %） |
| 单独跑那一条 | passed | passed |
| 全量跑 | **876 passed / 164.11 s** | 910 passed / 163.30 s（那一次 backfill 61.58 s 红）；再跑一次 **910 passed / 147.85 s** 全绿 |

⚠️ 那 57 s 的 setup **就是**整学期回放的所在（测试体只断言夹具里量出来的 `elapsed`），
故「setup 只差 0.3 %」就是「回放的耗时没有变」的直接证据；
机制上也讲得通：我在热路径上只加了**两次函数调用**（`_replace_previous` 与
`_prescription_values`），约 5.6 万张处方 × 2 次 × ~1.5 µs ≈ **0.17 s**。
全量跑之间的波动（147.85 s / 163.30 s / 170.77 s）与那条 60 s 阈值的余量本来就很薄
（Plan 02 记的基线是 28.4–34.0 s，硬规矩 #42 的线是 2×）。
⚠️ **已按要求清理 `git worktree`**（`git worktree list` 现在只剩主工作树一条）。

---

## ⑦ 最终验收

| 项 | 基线 | 现在 | 判据 |
|---|---|---|---|
| `python -m pytest -q` | 876 passed | **910 passed**（147.85 s，无并发负载时亲跑） | +34 = `test_prescription_api.py` 31 + `test_crud.py` 3 |
| `--cov=app.domain --cov-branch` 四格 | 996 / 0 / 288 / 0 / 100 % | **996 / 0 / 288 / 0 / 100 %**（**逐字不变**） | 带 `--cov` 时 `909 passed, 1 skipped`（基线 875+1，+34） |
| 表数 | 25（`prescription` 16 列） | **25**（`prescription` **16** 列） | `len(Base.metadata.tables)` / `len(list(Prescription.__table__.columns))` 运行时实读 |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33（没动）** | 本 Task 一个新表类都没加 |
| 架构守卫扫描面 | 49 | **50** | `pipeline 8 + db 11 + domain 16 + api 15`；涨的 1 个是 `app/api/routers/prescription.py` |
| `/api/` 路径模板数 | 47 | **51** | 从 `openapi()["paths"]` 实读；+4 就是本 Task 的四个端点 |
| `/api/` 上的操作数（path × method） | 73 | **77** | 同上 |
| detail 路径参数名 distinct | `['pk_value']` | **23 个**（见第 ③ 节清单） | 同上 |
| `components.securitySchemes` | 不存在 | **2 格** | 同上 |
| 三个指纹 | — | **逐字不变** | 见下表 |
| `git diff 9062b37 HEAD -- backend/data` | — | **空** | 一个字节都没动 |
| `backend/pe.db` | 不得存在 | **不存在** | 全程没起 uvicorn，`DEFAULT_DB_URL` 一次都没被解析过 |
| `backend/data/seed/` | 0 文件 | **0 文件** | — |

**三个指纹**（`sha256` 前 16 位大写，行尾归一化为 LF 之后计算；CRLF 计数用 `read_bytes()` 数）：

| 文件 | 指纹 | 字节 | CRLF |
|---|---|---|---|
| `national_standard_2014.csv` | `D2C8E539E2FA0029` | 21412 | 0 |
| `exercises.yaml` | `5394B37F01DAC9AC` | 23247 | 0 |
| `exercise_equivalence.yaml` | `822CB86A5E998301` | 8245 | 0 |

三个值与派单给的 `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` **逐字相同**。

⚠️ **没跑过** `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`
（三个禁区命令）；`tests/pipeline/test_backfill.py` 是**测试**自己在内存/临时库里跑回放，
不写 `backend/data/`。

⚠️ **工作树的行尾是混合的**（`git ls-files --eol` 实读：索引里一律 `i/lf`，
而工作树上 `deps.py` / `prescription_stage.py` / `main.py` 是 `w/crlf`、
`crud.py` / `catalog.py` / `schemas/prescription.py` / `routers/__init__.py` /
`test_crud.py` 是 `w/lf`）。⚠️ **这个混合在基线上就存在**（`main.py` 我一个字节都没动，
它本来就是 CRLF），且每个文件**内部**是统一的（逐个数过：CRLF 计数 == LF 计数），
故没有引入「一个文件里两种行尾」。`git diff --stat` 也证实了这一点：
改动的行数是 94 / 101 / 17 / 9 / 223 / 701 / 194，**不是**整文件重写。

---

## ⑧ commit sha

```
9062b37 docs: Plan03 Task 4 预检 —— 1 Critical（WeeklySheet 不能 JSON 化）+ 3 个前后端对接缺口，计划更正 6 处（Ruling 10 + 硬规矩 #104）
e2a0803 docs(sdd): Plan03 Task 3 结案 —— 876 passed，47 个端点/23 个资源全落地，Ruling 9 + 硬规矩 #103 + 控制者错误 #7-#12（顶回 7 处全采纳，累计 38/38）
e88afaf docs: Plan03 Task 3 结案 —— 876 passed，23 个资源全部落地，顶回 7 处（含读写矩阵计数 9/14 与 12/10/1）
9a62a93 test(api): Plan03 Task 3 ④  收尾 —— upsert 回滚守卫 + 两个无调用方参数的守卫
7fa8ecf feat(api): Plan03 Task 3 ③  catalog 的 23 行 RESOURCES + 17 条遍历型守卫
```

（上面是 `git log --oneline -5` 在**写本报告之前**的输出，故三个新 commit 还不在里面；
它们的 sha 由控制者在收到本报告后自行 `git log` 取。三个 commit 的信息正文分别是：
①`feat(api): Plan03 Task 4 (1/3) —— P4-A1 投影的唯一所有者 + P4-A5 securityScheme + P4-A6 pk_alias`、
②`feat(api): Plan03 Task 4 (2/3) —— 处方侧四个特例端点`、
③`docs(sdd): Plan03 Task 4 结案报告 …`（就是本报告）。**没有 push。**）
