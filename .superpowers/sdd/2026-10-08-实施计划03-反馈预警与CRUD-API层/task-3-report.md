# Task 3 报告 — 泛型 CRUD 工厂 + 23 个资源

**实现者**：Task 3 子代理　**分支**：`feature/plan-03-feedback-alert-crud-api`
**基线 commit**：`40a7a0e`　**结案 commit**：`9a62a93`　**fix round**：**0 轮**（一次跑通）
**顶回控制者**：**7 处**（第 ⑥ 节）　**没按派单做的地方**：**8 处**（第 ⑥ 节）

---

## ① 环境与基线复现

**开工第一件事（硬规矩 #73）** —— import 冒烟，一次通过，**没有** `ImportError: DLL load failed`：

```
cd backend
python -c "import sqlalchemy, fastapi, uvicorn, httpx, pydantic, yaml; print(...)"
→ 2.1.3 0.141.1 0.54.0 0.28.1 2.13.5 6.0.3
```

| 组件 | 实测版本 | 与简报一致 |
|---|---|---|
| Python | 3.11.1（无 venv） | ✅ |
| SQLAlchemy | **2.1.3** | ✅ |
| FastAPI | **0.141.1** | ✅ |
| uvicorn | 0.54.0 | ✅ |
| httpx | 0.28.1 | ✅ |
| Pydantic | **2.13.5** | ✅ |
| PyYAML | 6.0.3 | ✅ |

Starlette 的版本没有直接打印（它是 FastAPI 的传递依赖）；简报说 1.7.0，
本 Task 未做任何依赖它具体版本的判断，故未复核。

**基线复现**（开工时在 `40a7a0e` 上亲跑）：

| 项 | 简报给的基线 | 开工实测 | 结案实测 |
|---|---|---|---|
| `python -m pytest -q` | 845 passed | 845 passed | **876 passed** |
| 带 `--cov` | 844 passed, 1 skipped | — | **875 passed, 1 skipped** |
| `app/domain` 四格 | 996 / 0 / 288 / 0 / 100% | — | **996 / 0 / 288 / 0 / 100%**（逐字不变） |
| 表数 | 25 | 25 | **25**（本 Task 不建表） |
| `_MODELS_PUBLIC_BASELINE` | 33（不动） | 33 | **33**（不动） |
| 架构守卫扫描面 | 38 | 38 | **49** |
| 工作树 | 干净 | 干净 | 干净 |

⚠️ `len([n for n in dir(models) if not n.startswith("_")])` 实测是 **39**，
= 基线 33 + **6 个子模块名**（`organisation` / `assessment` / `derived` / `ops` /
`feedback` / `prescription`）。守卫 `test_models_public_namespace_is_unchanged_by_the_split`
自己就把那 6 个排除在外（`observed - _MODELS_SUBMODULES == set(_MODELS_PUBLIC_BASELINE)`），
故 33 与 39 不是矛盾、是两个口径。**基线常量一个字节都没动。**

**扫描面 38 → 49** 的构成（`app/` 下按目录 `rglob("*.py")`，运行时口径）：

```
pipeline 8 + db 11 + domain 16 + api 14 = 49      （api 从 3 涨到 14）
```

`api` 那 14 个 = Task 1 的 3 个（`__init__` / `deps` / `errors`）+ 本 Task 的 11 个
（`crud.py`、`schemas/` 8 个、`routers/` 2 个）。
⚠️ 守卫 `test_production_layers_never_import_app_seed` 的下界断言是 `>= 18`
（Task 1 一次抬到位，账本 S6：「后面 8 个 Task 不再动它」），**18 ≤ 49 仍成立，本 Task 没改它**。
`test_api_layer_dependency_direction_is_one_way` 的两个下界（`api >= 3`、反向 `>= 15`）
与那条绿档断言（`"app.db.models.organisation" in api_folded`）同样没动，全部仍绿。

**禁区**（第 ⑦ 节有逐条复核）：全程没有跑 `app.seed.generate` / `app.pipeline.backfill` /
`app.pipeline.daily`；没有起过 uvicorn；所有 HTTP 面验证都跑在 `tests/api/conftest.py` 的
内存库（`sqlite://` + `StaticPool`）上。

---

## ② `build_crud_router` 的最终签名与 `CrudSchemas` 的字段

`inspect.signature(build_crud_router)` 的原样输出（全部 `KEYWORD_ONLY`）：

```
(*, model: type[typing.Any],
    schemas: app.api.crud.CrudSchemas,
    path: str,
    tags: list[str],
    pk: str = 'id',
    order_by: str = 'id',
    readable: bool = True,
    writable: bool = True,
    on_delete: str = 'restrict',
    natural_key: tuple[str, ...] | None,          ← ⚠️ 无缺省值（刻意）
    list_exclude: tuple[str, ...] | None = None,
    scope: collections.abc.Callable[[sqlalchemy.orm.session.Session, typing.Any,
                                     int | None, str | None], None] | None = None
) -> fastapi.routing.APIRouter
```

与计划 Interfaces 逐格相同，包括「`natural_key` 无缺省、`list_exclude` 缺省 `None`」
这个不对称（Python 允许 keyword-only 的必填参数排在有缺省的参数之后）。
**那个不对称是承重的**：`on_delete` 有缺省值，故漏写会静默落到 `restrict`
（由 `test_every_resource_declares_on_delete_explicitly` 兜住）；
而 `natural_key` 没有缺省值，漏写是**当场 `TypeError`**——
静默落到「无自然键」的后果是 POST 走裸 `session.add`、重复行悄悄进库，
那比一次 `TypeError` 贵得多。

`dataclasses.fields(CrudSchemas)`（`frozen=True`）：

| 字段 | 类型 | 缺省 |
|---|---|---|
| `read` | `type[pydantic.main.BaseModel]` | **无**（必填） |
| `create` | `type[pydantic.main.BaseModel] \| None` | `None` |
| `update` | `type[pydantic.main.BaseModel] \| None` | `None` |

**工厂体里的五道配置校验**（全部在**导入期**响，因为 `catalog.py` 在模块体里调 23 次工厂；
失败的形状是「uvicorn 起不来 / pytest 收集期就炸」，不是「某个端点运行时炸」）：

1. `on_delete not in {"restrict","cascade","forbid"}` → `ValueError`
2. `writable=True` 而 `create`/`update` 有 `None` → `ValueError`
3. `writable=False` 而 `on_delete="cascade"` → `ValueError`（DELETE 端点根本不注册，cascade 无从生效）
4. `pk` / `order_by` / `natural_key` / `list_exclude` 里有该表不存在的列 → `ValueError`（点名是哪几列）
5. `path` 不以 `/api/` 开头 → `ValueError`

⚠️ 第 3 与第 5 条**是本 Task 自己加的**（派单没要求），第 5 条落地当天就抓到了一次
自己的错：`scope` 那条测试原本把探针挂在 `/probe/training-logs`，被这道校验当场拦下。
守卫是 `test_the_factory_rejects_a_bad_configuration`（六道 `pytest.raises` + 一个绿档）。

**另有四个模块级私有函数**（都被测试直接调用，不是死代码）：

| 函数 | 职责 | 守卫 |
|---|---|---|
| `_json_text_columns(model)` | `list_exclude` 的自动探测（P3-B3） | `test_every_resource_list_omits_json_text_columns_and_read_one_includes_them` |
| `_child_tables(model)` / `_child_tables_of(table)` | **入向**外键，排除 `SET NULL`/`CASCADE`（P3-B4） | `test_child_tables_skips_the_foreign_keys_that_clear_themselves` |
| `_purge_where(session, table, condition)` | `cascade` 的递归删除（**子表先删**，P7-A4） | `test_on_delete_cascade_deletes_children_first` |
| `_get_or_404(session, model, pk_value)` | `session.get` + 显式 404（P3-B7） | `test_read_a_missing_pk_is_404` |
| `_conflict_message(table_name, natural_key)` | 409 的消息，**只引列名**（P3-B5） | `test_a_conflict_message_names_the_key_columns_and_never_the_literal_none` |

**三个 `ON_DELETE_*` 常量**是「哪三档」的唯一所有者：`catalog.py` 的 23 行、
工厂的校验、与那条计数守卫都读它们，不再出现第二份字面量。

---

## ③ `RESOURCES` 的 23 行逐个落地情况

全部 23 行都落地了。下表每一格都是**运行时读回来的**（`spec["model"].__module__`、
`spec["natural_key"]`、`_json_text_columns(...)`、`_child_tables(...)`），
不是从源码抄的（硬规矩 #89）。`list_exclude` 一列给的是**自动探测的结果**——
23 行**没有一行**显式传 `list_exclude`（实测计数 0）。

| # | 路径 | 表 | 模型类 | **import 路径** | 列 | `natural_key` | 可写 | `on_delete` | `list_exclude`（自动探测） | 入向子表 |
|--:|---|---|---|---|--:|---|---|---|---|---|
| 1 | `/api/semesters` | `semester` | `Semester` | `app.db.models` | 6 | `(name)` ⚠️无名约束 | ✅ | `forbid` | — | 9 张 |
| 2 | `/api/teachers` | `teacher` | `Teacher` | `app.db.models` | 3 | `(staff_no)` ⚠️无名 | ✅ | `restrict` | — | `course_section` |
| 3 | `/api/students` | `student` | `Student` | `app.db.models` | 7 | `(student_no)` ⚠️无名 | ✅ | `restrict` | — | 12 张 |
| 4 | `/api/course-sections` | `course_section` | `CourseSection` | `app.db.models` | 6 | **`None`** | ✅ | `restrict` | — | 4 张 |
| 5 | `/api/enrollments` | `enrollment` | `Enrollment` | `app.db.models` | 4 | `(semester_id, student_id, course_section_id)` | ✅ | `restrict` | — | 无 |
| 6 | `/api/fitness-test-batches` | `fitness_test_batch` | `FitnessTestBatch` | `app.db.models` | 6 | **`None`** | ✅ | `restrict` | — | `fitness_test_result` |
| 7 | `/api/fitness-test-results` | `fitness_test_result` | `FitnessTestResult` | `app.db.models` | **21** | `(test_batch_id, student_id)` | ❌ | `forbid` | — | 无 |
| 8 | `/api/body-compositions` | `body_composition` | `BodyComposition` | `app.db.models` | 8 | `(student_id, measured_on)` | ✅ | `restrict` | — | 无 |
| 9 | `/api/interest-surveys` | `interest_survey` | `InterestSurvey` | `app.db.models` | 7 | `(student_id, semester_id, filled_on)` | ✅ | `restrict` | `dimensions`, `raw_answers` | 无 |
| 10 | `/api/percentile-snapshots` | `percentile_snapshot` | `PercentileSnapshot` | `app.db.models` | 14 | `(semester_id, computed_on, item, sex, age_group)` | ❌ | `forbid` | — | 无 |
| 11 | `/api/derived-metrics` | `derived_metrics` | `DerivedMetrics` | `app.db.models` | 11 | `(student_id, computed_on)` | ❌ | `forbid` | `annual_change`, `weaknesses`, `body_comp_reasons` | 无 |
| 12 | `/api/stratification-results` | `stratification_result` | `StratificationResult` | `app.db.models` | 10 | `(student_id, computed_on)` | ❌ | `forbid` | `input_snapshot` | 无 |
| 13 | `/api/exercises` | `exercise` | `Exercise` | **`app.db.models.prescription`** | 7 | `(ref)` ⚠️无名 | ❌ | `forbid` | `targets` | 无 |
| 14 | `/api/prescription-templates` | `prescription_template` | `PrescriptionTemplate` | **`app.db.models.prescription`** | 10 | `(template_ref)` ⚠️无名 | ❌ | `forbid` | — | 无 |
| 15 | `/api/prescriptions` | `prescription` | `Prescription` | **`app.db.models.prescription`** | 16 | `(student_id, generated_on)` | ❌ | `restrict` | **5 个**：`training_package`, `assembly_snapshot`, `safety_substitutions`, `teacher_overrides`, `trigger_reasons` | `weekly_adjustment` |
| 16 | `/api/weekly-adjustments` | `weekly_adjustment` | `WeeklyAdjustment` | **`app.db.models.prescription`** | 8 | `(prescription_id, week, reason, source)` | ❌ | `restrict` | — | 无 |
| 17 | `/api/class-sessions` | `class_session` | `ClassSession` | **`app.db.models.feedback`** | 7 | `(course_section_id, session_date, period)` | ✅ | **`cascade`** | — | `rpe_record` |
| 18 | `/api/rpe-records` | `rpe_record` | `RpeRecord` | **`app.db.models.feedback`** | 6 | `(class_session_id, student_id)` | ❌ | `restrict` | — | 无 |
| 19 | `/api/training-logs` | `training_log` | `TrainingLog` | **`app.db.models.feedback`** | 10 | `(student_id, log_date)` | ❌ | `restrict` | — | 无 |
| 20 | `/api/mini-tests` | `mini_test` | `MiniTest` | **`app.db.models.feedback`** | 10 | `(student_id, semester_id, week)` | ❌ | `restrict` | `item_combo` | 无 |
| 21 | `/api/alerts` | `alert` | `Alert` | **`app.db.models.feedback`** | 14 | `(rule_id, subject_key, semester_id, window_key)` | ❌ | **`forbid`**（P3-B8） | `trigger_snapshot` | **无**（`notification.alert_id` 带 SET NULL，被排除） |
| 22 | `/api/notifications` | `notification` | `Notification` | **`app.db.models.feedback`** | 10 | **`None`** | ❌ | **`forbid`**（P3-B8） | — | 无 |
| 23 | `/api/weekly-class-reports` | `weekly_class_report` | `WeeklyClassReport` | **`app.db.models.feedback`** | 12 | `(course_section_id, semester_id, week)` | ❌ | `forbid` | **5 个**：`layer_distribution`, `rpe_summary`, `checkin_rate_by_layer`, `progress_board`, `alert_summary` | 无 |

**`list_exclude` 的合计**：23 个资源上共 **19** 个 `JsonText` 列、分布在 **8** 张表
（`prescription` 与 `weekly_class_report` 各 5、`derived_metrics` 3、`interest_survey` 2，
`stratification_result` / `exercise` / `mini_test` / `alert` 各 1）。
⚠️ 全库是 **21** 个 / **9** 张表——多出的两个是 `cleaning_log.original_value` /
`processed_value`，而 `cleaning_log` **不是** 23 个资源之一（见第 ⑥ 节顶回 3）。

**P3-B1 的落地（本 Task 唯一的 Critical）**：11 个子模块 import **全部走对**，
`prescription` 4 个（第 13–16 行）+ `feedback` 7 个（第 17–23 行）；
其余 12 行走 `from app.db import models`。
守卫 `test_the_eleven_non_public_models_are_reached_through_their_submodules` 从**三个侧面**钉：
① 运行时 `model.__module__` 逐个对到字面期望；
② 那 11 个 `hasattr(models, 名字) is False` 且 `not in models.__all__`
　（于是「有人把它们重导出进公有面了」也会红 —— Ruling 97）；
③ **AST**（不是正则数命中数，硬规矩 #89 再扩写）：`catalog.py` 里确有两条
　`ImportFrom(module="app.db.models.feedback"/"…prescription", level=0)` 导入那 11 个名字，
　且 `models.X` 这种属性访问**恰好 12 处**、`isdisjoint(那 11 个)`。

**schema 侧**：41 个 Pydantic 模型 = 9 个可写资源的三件套（27）+ 14 个只读资源的 `*Read`（14）。
`test_every_read_schema_covers_exactly_the_model_columns` 断言 41 个模型的
`model_fields` **逐字等于**（含声明顺序）该表的列名清单 / 列名清单减 `id`，
且 `*Update` 的每个字段都**有缺省值**（`exclude_unset` 语义的前提）。
两侧不同源：`BaseModel.model_fields`（Pydantic）vs `table.columns`（SQLAlchemy）。
探针在写测试之前先跑过一遍：`资源数 23 | 模型数 41 | 全部 41 个模型字段集逐字对齐（含顺序）`。

**OpenAPI 面的独立复核**（不是从 `RESOURCES` 反推）：

```
paths 47 = 23 个 list + 23 个 detail + /api/health
按方法：get 47 / post 9 / patch 9 / delete 8 / put 0     合计 73（含 health 的 1 个 GET）
→ CRUD 端点 72 个 = 23×5(115) − 14 个只读的 3 个写方法(42) − semesters 的 1 个 DELETE
detail 路径的方法组合分布 = {('get',): 14, ('get','patch','delete'): 8, ('get','patch'): 1}
list   路径的方法组合分布 = {('get',): 14, ('get','post'): 9}
detail 路径的参数名一律是 {pk_value}
components.schemas = 43（41 个模型 + Page + HTTPValidationError）
```

`delete 8 = 9 − 1` 正是「`semesters` 可写但 `on_delete="forbid"`」那一格，
`('get','patch')` 那一组也只有它一个 —— 两个开关（`writable` / `on_delete`）互相独立，
在 OpenAPI 面上看得清清楚楚。

⚠️ **一个踩到的框架事实**：FastAPI 0.141.1 的 `include_router` 是**惰性**的，
它往 `app.routes` 里塞一个 `_IncludedRouter` 包装对象而不是把子路由摊平。
实测 `len(create_app().routes) == 6`、`api_router.routes == 1`、`catalog_router.routes == 23`。
**故「注册了多少个端点」不能用 `len(app.routes)` 数**，必须走 `/openapi.json`。
上面那组数字全部是 OpenAPI 口径。

---

## ④ `_child_tables` 的实现与「排除 SET NULL/CASCADE」那条测试

**为什么需要它**：`on_delete="restrict"` 要「点名是哪张子表挡住的」，
而**子表清单不在模型上** —— `model.__table__.foreign_keys` 给的是**出向**外键（我指向谁），
入向（谁指向我）只能扫 `Base.metadata` 的全部 25 张表。

**实现**（表级 `_child_tables_of(table)` + 模型级 `_child_tables(model)` 的薄包装）：

```python
for other in Base.metadata.tables.values():
    for foreign_key in other.foreign_keys:
        if foreign_key.column.table is not table:
            continue                                    # 出向的、或指向别的表的
        if (foreign_key.ondelete or "").upper() in _SELF_CLEARING_ONDELETE:
            continue                                    # DB 自己会处理，故它挡不住删除
        found.append((other.name, foreign_key.parent.name))
return sorted(set(found))
```

`_SELF_CLEARING_ONDELETE = frozenset({"SET NULL", "CASCADE"})`。

**⚠️ 排除那一支是 P3-B4 的全部内容**：实测 `notification.alert_id` 与
`notification.prescription_id` 都带 `ondelete="SET NULL"`（Plan 03 Task 2 的顶回 3 加的）。
不排除的话 `_child_tables(Alert)` 会返回 `[("notification", "alert_id")]`，
于是删一条 `alert` 时报「1 行 notification 仍指向它」—— **一句假话**，
而且它挡住的是一次本来能成功的删除（SQLite 自己会把那两列置 NULL）。

**⚠️ 一个必须说清的细节**：`alert` 与 `notification` 的 `on_delete` 是 `forbid`（P3-B8），
故那个假 409 在它们身上**今天打不出来**（DELETE 端点根本不注册）。
**打得出来的是 `prescriptions`**：它的 `on_delete` 是 `restrict`、
而它同时有 `weekly_adjustment`（`ondelete=None`，真的会挡）与
`notification`（`SET NULL`，不该挡）两个入向外键。
不排除的话，「一条有通知指向、但没有微调行的处方」会得到一个假 409。

**`"CASCADE"` 那一档今天是许可而不是断言**（硬规矩 #39）：实测**全库没有一个外键带
DB 级 `CASCADE`**，25 张表的 20 个外键的 `ondelete` 取值集合恰好是 `{None, "SET NULL"}`。
把它列进 `_SELF_CLEARING_ONDELETE` 的理由是：`on_delete="cascade"` 那一档由
`_purge_where` **自己**删子行，若将来有人给某个外键加了 DB 级 `CASCADE`，
两边就会各删一次（第二次是空操作、不炸，但「谁负责删」变成两个所有者）。

**那条测试**：`tests/api/test_crud.py::test_child_tables_skips_the_foreign_keys_that_clear_themselves`

两侧不同源：期望侧是**就地扫 `Base.metadata` 数原始入向外键**（连 `ondelete` 一起打出来），
被测侧是 `_child_tables`。它钉住五格：

```python
raw_inbound("alert")         == [("notification", "alert_id", "SET NULL")]     # 原始事实
raw_inbound("prescription")  == [("notification", "prescription_id", "SET NULL"),
                                 ("weekly_adjustment", "prescription_id", None)]
_child_tables(Alert)         == []                                            # ← 被跳过了
_child_tables(Prescription)  == [("weekly_adjustment", "prescription_id")]     # ← 只留真的会挡的
_child_tables(ClassSession)  == [("rpe_record", "class_session_id")]
raw_inbound("student") == [(n, c, None) for n, c in _child_tables(Student)]    # 12 个一个都不许漏
{fk.ondelete for 全库} == {None, "SET NULL"}                                   # CASCADE 那档今天不可达
```

**变异自证（这条守卫不是恒绿的）**：把 `_child_tables_of` 里那句
`in _SELF_CLEARING_ONDELETE` 改成 `in frozenset()`（即不排除），
本条**当场红**，报的正是 P3-B4 预言的那句假话的形状：

```
FAILED test_child_tables_skips_the_foreign_keys_that_clear_themselves
  AssertionError: assert [('notification', 'alert_id')] == []
  Left contains one more item: ('notification', 'alert_id')
```

改回后全绿。全仓已用 `Grep MUTATION|_MUTATED` 复核**零残留**。

**`_purge_where`（cascade 那一档）**：递归、**子表先删**（P7-A4）。
先用 `select(pk).where(condition)` 取出待删行的主键，递归删各子表里指向它们的行，
最后才 `delete(table)`。空集时立即返回（既是递归终止条件，也避免发一条
`WHERE … IN ()` 的废语句）。
⚠️ 它取主键用的是 `next(iter(table.primary_key.columns))`，
前提是「单列主键」—— 那是一条**没人看着就会静默出错**的假设
（复合主键会让它只按第一列删，**删多了且不报错**），故本 Task 把它写成守卫
`test_every_table_has_a_single_column_primary_key`（25 张表逐个断言，且主键名集合 == `{"id"}`）。
⚠️ 递归的**深度 ≥ 2 那一条边今天没有测试覆盖**：唯一的 cascade 用户是
`class_session → rpe_record`，而 `rpe_record` 没有子表。图上可达的深度 2 形状是
`student → prescription → weekly_adjustment`，但 `students` 是 `restrict`、永远走不到
`_purge_where`。已写进那个函数的 docstring。

---

## ⑤ 三个计数的实测复核 —— ⚠️ 与派单给的数不同（顶回 2）

**实测（三个互相独立的口径，逐个吻合）**：

| 口径 | 可写 | 只读 | `restrict` | `forbid` | `cascade` |
|---|--:|--:|--:|--:|--:|
| ① `RESOURCES` 逐行计数 | **9** | **14** | **12** | **10** | **1** |
| ② OpenAPI 的方法数（`post` / `patch` = 可写数；`delete` = 可写 − forbid 的可写数） | 9 / 9 | — | — | — | — |
| ③ OpenAPI 的 detail 路径方法组合分布 | `{get,patch,delete}`: **8**　`{get,patch}`: **1** | `{get}`: **14** | — | — | — |

派单 §5 与简报 §4（P3-B8）/ §9 第 5 格逐字写的是「**可写 8 / 只读 15**；
`restrict` **11** / `forbid` **11** / `cascade` **1**」。**两组数都差一格。**

**逐行清单**（这是「自己数」的过程，控制者可以照着复核）：

* ✅ **可写 9 行**：`semesters` / `teachers` / `students` / `course-sections` /
  `enrollments` / `fitness-test-batches` / `body-compositions` / `interest-surveys` /
  `class-sessions`
* ❌ **只读 14 行**：`fitness-test-results` / `percentile-snapshots` / `derived-metrics` /
  `stratification-results` / `exercises` / `prescription-templates` / `prescriptions` /
  `weekly-adjustments` / `rpe-records` / `training-logs` / `mini-tests` / `alerts` /
  `notifications` / `weekly-class-reports`
* `restrict` **12 行**：`teachers` / `students` / `course-sections` / `enrollments` /
  `fitness-test-batches` / `body-compositions` / `interest-surveys` / `prescriptions` /
  `weekly-adjustments` / `rpe-records` / `training-logs` / `mini-tests`
* `forbid` **10 行**：`semesters` / `fitness-test-results` / `percentile-snapshots` /
  `derived-metrics` / `stratification-results` / `exercises` / `prescription-templates` /
  `alerts` / `notifications` / `weekly-class-reports`
* `cascade` **1 行**：`class-sessions`

9 + 14 = 23　　12 + 10 + 1 = 23　　✅

**为什么派单的数对不上**：读写矩阵（简报第 268–290 行那 23 行）**已经应用过 P3-B8** ——
第 21/22 行的 `on_delete` 格里就逐字印着「**`forbid`（P3-B8 更正，原为 `restrict`）**」。
故按矩阵数出来的就是更正后的值。而 P3-B8 说「原为 12/10/1 → 更正后 11/11/1」：

* 「更正后 11/11」与矩阵不符（矩阵是 12/10）；
* 「原为 12/10」也与矩阵不符 —— 把 `alerts` 与 `notifications` 两行改回 `restrict`，
  更正前应是 **14 / 8 / 1**。

即 P3-B8 的那一句把「挪 2 行」算成了「挪 1 行」。
计划正文第 293 行自己也逐字要求「**数字自己数、不要照抄本行**（硬规矩 #44/#89）」，
本 Task 就是照那句话办的。

**同一族的另一处**：计划正文「只读资源：**15 个**」那半句，
而它紧接着自己列出来的是 4（批处理产物）+ 1（`fitness_test_result`）+ 2（参考数据）
+ 7（有特例写入口）= **14** 个。**散文的数与散文自己列的清单差一格。**

**那条计数守卫**：`test_the_read_write_matrix_counts_are_pinned`。
期望值一律**字面写死**（硬规矩 #35），且不只钉三个数，还钉两份**排序后的路径清单**
（9 个可写的、10 个 `forbid` 的）—— 后者把 P3-B8 的落点（`alerts` 与 `notifications`
在 `forbid` 这一档里）也钉住了。它的 docstring 把上面这段逐行清单与「为什么派单的数对不上」
一并抄了进去，故下一个人不必回到简报去比对。

⚠️ **`cascade` 只有 1 个用户**这条也被单独钉住：
`[s["path"] for s in RESOURCES if s["on_delete"] == ON_DELETE_CASCADE] == ["/api/class-sessions"]`。
计划提到的另一处 cascade（`prescriptions` → `weekly_adjustment`）**不经过 DELETE 端点**
（`prescriptions` 是 `restrict`），由 Task 4 的「处方被替换」路径内部使用；
实测 `_child_tables(Prescription) == [("weekly_adjustment", "prescription_id")]`，
故有微调行的处方从 API 删会得到 409 并点名 `weekly_adjustment` —— 与设计一致。

---

## ⑥ 待清扫 / 关切 / 没按派单做的地方 / 顶回控制者的地方

### ⑥.1 顶回控制者的地方（**7 处**）

**顶回 1（Important）——派单的 `Files: Create` 清单少了 2 个 schema 模块，本 Task 建了 3 个额外文件。**
派单第 5 节逐字是「`backend/app/api/schemas/{__init__,organisation,assessment,derived,prescription}.py`」
—— **4 个模块 + `__init__`**。而本 Task 要落地全部 23 个资源，其中 **7 个**
（`class_session` / `rpe_record` / `training_log` / `mini_test` / `alert` / `notification` /
`weekly_class_report`）的 schema 在那 4 个模块里**没有住址**。
计划的 File Structure 确实列了 `schemas/feedback.py`（4 个）与 `schemas/alerts.py`（3 个），
是 Task 3 的 `Files` 那一行漏抄了。**处置：按 File Structure 补建这两个**
（而不是把 7 个塞进 `prescription.py`，那是语义错误）。
另加 `schemas/_base.py`（`ReadModel` + `one_of` 两个跨模块共享件），
**先例是 `app/db/models/_shared.py`** —— 那个模块的 docstring 逐字给了理由
（「塞进任何一个都会让另外几个为了拿一个工具而 import 一个与它毫无关系的小节」），
本包 7 个模块同一条。⚠️ 刻意**不**把 `ReadModel` 放进 `schemas/__init__.py`：
那会造成「`__init__` 定义基类 → 底部星号导入子模块 → 子模块回头 `from app.api.schemas import ReadModel`」
的部分初始化依赖，能跑但脆。

**顶回 2（Important）——读写矩阵的三个计数。** 见第 ⑤ 节全节。
实测 **9 / 14**、**12 / 10 / 1**，不是派单的 8 / 15、11 / 11 / 1。

**顶回 3（Minor）——P3-B3 的「21 个、8 张表」混用了两个口径。**
实测：全库 `JsonText` 列 **21** 个、分布在 **9** 张表
（`interest_survey` 2、`derived_metrics` 3、`stratification_result` 1、`cleaning_log` **2**、
`exercise` 1、`prescription` 5、`mini_test` 1、`alert` 1、`weekly_class_report` 5）。
**23 个资源上是 19 个、8 张表** —— 差的那 2 个是 `cleaning_log.original_value` /
`processed_value`，而 `cleaning_log` **不是** 23 个资源之一。
简报把「全库总数 21」与「资源上的分布 8 张表」写在同一句里。
**自动探测天然不受影响**（它按模型逐张探测，从不合计），
但报告、`crud.py` 的 docstring 与那条守卫的字面清单都必须用对的数：
`_JSON_TEXT_COLUMNS` 合计 **19**、表数 **8**，守卫末尾 `assert running_total == 19`。

**顶回 4（Important）——P3-B2 的「409 测试对 20 个资源写、反向测试对 3 个写」在 HTTP 面上不可达。**
20 个有自然键的资源里 **13 个是只读的**（`writable=False` → POST 根本不注册 → 405），
撞键**无从发生**；能在 HTTP 面上验 409 的只有 **7** 个（可写 ∧ 有自然键：
`semesters` / `teachers` / `students` / `enrollments` / `body-compositions` /
`interest-surveys` / `class-sessions`）。
反向那一条同理：3 个无自然键的资源里 `notifications` 是只读的，
只有 **2** 个（`course-sections` / `fitness-test-batches`）能在 HTTP 面上验
「同一个请求体连发两次都 201」。
**处置**：HTTP 面覆盖 7 + 2 个，**结构面遍历全部 20 / 3** ——
`test_a_conflict_message_names_the_key_columns_and_never_the_literal_none`
对 20 个逐个断言消息含全部键列名、不含字面 `"None"`、含表名；
`test_natural_key_is_a_real_unique_constraint_of_that_table` 对 23 个逐个断言
`spec["natural_key"] == 从 Base.metadata 读出的唯一约束列`（两侧不同源），
并断言「恰好 3 张资源表没有唯一约束」。
`test_a_resource_without_a_natural_key_never_returns_409` 的 docstring 里
**显式写明了这个不对称**（`notifications` 为什么只能从结构面断言），
免得下一个人以为漏测了一个。

**顶回 5（Important）——「POST 走 `repo.upsert`」与「撞键 → 409」在 `upsert` 的实际语义下不可同时成立。**
`repo.upsert` 的语义是「有则更新、无则插入」，**它撞键时不抛异常、而是改掉那一行并返回它**。
**处置**：调 `upsert`（满足派单的字面），然后用 `obj not in session.new` 判定
「返回的是不是新行」（新插入的实例在 flush 前是 *pending*、在 `session.new` 里；
已存在的那一行是 *persistent*、不在），不是新行就 **`session.rollback()` + 409**。
⚠️ **回滚是承重的**：`upsert` 的更新分支已经 `setattr` 过那一行了，
不回滚就等于「一次被拒绝的 POST 改掉了库里的数据」，而响应体是 409、
前端会当成「什么都没发生」。守卫是 `test_create_with_a_duplicate_natural_key_is_409`
的最后一拍（用「同 `name`、`weeks=99`」撞一次，再把原行读回来比 `weeks == 16`）。
**这一拍是 commit ④ 补的** —— commit ① 的版本只断言了「没有多出一行」，
那证明不了「已有行没被改」。

**顶回 6（Minor）——计划 Step 1 把三条错误映射测试列进 `tests/api/test_crud.py`，它们已经存在了。**
`test_a_domain_value_error_becomes_422_with_its_message` /
`test_an_integrity_error_becomes_409` /
`test_an_unhandled_error_becomes_500_without_a_stack_trace`
已由 Plan 03 Task 1 交付在 `tests/test_main.py`
（`test_domain_value_error_maps_to_422` / `test_integrity_error_maps_to_409` /
`test_unhandled_exception_maps_to_500_without_leaking_the_stack`），
被测对象是 `register_error_handlers` 的**接线**。
**处置：不重复**（那会是同一份期望值的第二个所有者），
本文件只测 **CRUD 自己会抛的那几个码**（404 / 409 / 405 / 422），
它们同样穿过那份统一形状 —— 例如 405 那一档顺带把 `errors.py` 的
`http_<码>` 兜底规则第一次在真端点上钉住（`code == "http_405"`，
而 `errors.py` 的 `_CODE_BY_STATUS` 注释举的例子正是 405）。
理由写在 `test_crud.py` 的模块 docstring 里。

**顶回 7（Minor）——计划 Step 1 用 `semester` 测 `test_delete_returns_204_and_the_row_is_gone`，写不出来。**
读写矩阵第 1 行给 `semesters` 的 `on_delete` 是 **`forbid`**，
故它的 DELETE 端点根本不注册、打过去是 **405** 而不是 204。
**处置**：那条测试改用 `teachers`（可写 + `restrict` + 今天没有子行，
是「真的能删成功」那一档里最简单的一个），
并**另加一条** `test_a_forbidden_delete_is_405_even_on_a_writable_resource`
由 `semesters` 承担 —— 它钉的是「`writable` 与 `on_delete` 是**两个独立开关**」
（`forbid` 只关 DELETE，不顺手关掉 PATCH/POST）。
`test_crud.py` 的模块 docstring 里逐字交代了这次替换与理由。

### ⑥.2 没按派单做的地方（**8 处**）

1. **多建了 3 个文件**：`schemas/_base.py`、`schemas/feedback.py`、`schemas/alerts.py`
   （顶回 1；前两个在 File Structure 里、`_base.py` 不在）。
2. **工厂体里加了两道派单没要求的配置校验**：
   `writable=False ∧ on_delete="cascade"` → `ValueError`；
   `path` 不以 `/api/` 开头 → `ValueError`。后者落地当天就抓到自己一次
   （`scope` 探针原本挂在 `/probe/…`）。
3. **三处枚举列加了 Pydantic 侧校验**（`student.sex` / `course_section.grouping_mode` /
   `fitness_test_batch.timepoint`，`*Create` 与 `*Update` 各一个，共 6 个校验器），
   经 `schemas/_base.py` 的 `one_of` 助手。**词表的唯一所有者仍是模型类常量**
   （`Student.SEXES` 一类，校验器把那个集合**传**进去、不声明第二份）。
   目的是把「送了一个域外值」从 DB 的 `IntegrityError` → **409 integrity_conflict**
   挪回请求校验的 **422**：前端表单填错一个下拉框时收到「与别人撞了」，
   它会去查「谁跟我重复」，而真正的问题是它自己送了一个不存在的值。
   守卫 `test_a_value_outside_the_model_domain_is_422_not_409`（红绿两档 + PATCH 那一档）。
   ⚠️ **只覆盖这 3 列**：其余 CHECK 约束的列都在只读资源上（`*Create` 不存在），
   或者取值域是开放集合（`training_log.source` 刻意没有 CHECK）。
4. **list 端点没有 `response_model`**：改成显式只 SELECT 保留的列 + 手工拼 dict +
   `jsonable_encoder`。理由是 P3-B3 的性能诉求**只有在 SQL 层不 SELECT 那些列时才算兑现** ——
   一个含全部列的 `response_model` 会让 FastAPI 在序列化阶段 `getattr` 每个字段，
   被 `defer` 掉的列于是触发 N+1 延迟加载，收益当场归零。
   **代价（已写进那个端点的 docstring）**：OpenAPI 里 list 的响应 schema 是空的，
   前端要字段清单请看同一资源的 `GET {path}/{pk}`（那是 `schemas.read`，
   而 list 的键集合恰好是它减去 `list_exclude`）。
   ⚠️ 键名与 JSON 编码结果和 `response_model` 那条路径**逐字相同**
   （`jsonable_encoder` 把 `date`/`datetime` 折成 ISO 串，与 Pydantic 的序列化一致），
   这一点由 `test_every_resource_list_omits_json_text_columns_and_read_one_includes_them`
   的 `set(one) - set(item) == set(detected)` 与
   `set(item) == 全部列 − detected` 两行间接钉住（23 个资源逐个）。
5. **不加 `?order_by=` / `?desc=` 查询参数**：`order_by` 是**工厂参数**（23 行全用缺省 `"id"`），
   端点上没有排序查询参数。于是「分页 + 排序」的读法是
   「返回的 items 按 `order_by` 排好序」，不是「客户端可以选排序键」。
   理由：可选排序键要一份列名白名单 + 一条 422 分支，而一屏最多 200 行、客户端排序够用。
   Plan 04 若要服务端排序，那是给工厂加一个参数，不是改这 23 行。
6. **commit 分成 4 个**（派单建议 3–4）：① 工厂 + 4 个资源 + 12 条测试；
   ② 余下 4 个 schema 模块；③ `catalog` 扩到 23 行 + 17 条遍历型守卫；
   ④ 收尾（3 条补充守卫）。**刻意让 `catalog.py` 从 commit ① 起就是「23 行声明的唯一所有者」**，
   而不是先在测试里局部挂两个路由、commit ③ 再切过去 —— 那会让「资源声明」在两个 commit 里
   各有一份，是一次短暂的第二个所有者。
7. **`scope` 只挂在 `GET/PATCH/DELETE {path}/{pk}` 三个端点上**，list 与 create 不挂：
   `ScopeFn` 的第二个入参是「一个 ORM 行」，而 list 要的是**过滤**、create 时**行还不存在**，
   两者都不是这个签名能表达的。⚠️ 且那两个身份请求头**只在 `scope is not None` 时**
   才进 OpenAPI（依赖是条件注册的）—— 无条件注册的话 23 × 3 个端点会凭空多出两个头，
   Plan 04 的前端会以为每个 CRUD 都要传身份。守卫
   `test_the_scope_hook_rejects_a_mismatched_identity_with_403` 的最后一拍钉的就是这一格
   （`_parameter_names("/api/training-logs/{pk_value}") == {"pk_value"}`）。
8. **批次 C 那两条测试是派单没点名的**：`readable` 与 `list_exclude` 的显式覆盖
   在 23 行 `RESOURCES` 里**都是 0 个用户**（实测），按硬规矩 #39 它们要么删掉、
   要么写清「谁在用它、它守不住什么」。选了第三条路：**给它们各一条测试**，
   于是它们不是死代码。`test_an_explicit_list_exclude_overrides_the_auto_detection`
   刻意挑 `semester`（**一个 `JsonText` 列都没有**、自动探测结果是空元组），
   于是「`weeks` 从 list 里消失了」只能来自显式覆盖、不可能是探测的功劳。

### ⑥.3 关切（**9 条**，都不在本 Task 的修法范围内）

1. **`class_session.batch_id` 是 NOT NULL 外键指向 `daily_sync_run`，而后者不是 23 个资源之一。**
   于是教师建课次之前库里得先有一次 daily 运行，而前端**拿不到一份可选的批次列表**。
   本 Task **没有**替它发明缺省值：`batch_id: int = 0` 会当场
   `FOREIGN KEY constraint failed`（父表里没有 `id = 0` 的行 —— 硬规矩 #101 与
   Plan 03 Task 2 顶回 1 的那条：用哨兵值代替 NULL 之前必须先确认那一列不是外键），
   而把那一列改成可空是**改一张已结案的表**。原型口径是前端从
   `GET /api/class-sessions` 的既有行里读一个 `batch_id` 复用。
   ⚠️ **Task 9 的 `POST /api/pipeline/run-daily` 落地后这一格会缓解**（跑一次就有批次了）。
2. **`fitness_test_batch` 与 `course_section` 全表没有唯一约束**，故同一个
   `(semester_id, timepoint)` 可以被建两次。前者会让
   `percentile_stage`「挑 `<= as_of` 的最新一个 week1 批次」这一步有歧义。
   ⚠️ 加约束是**改 schema**（本仓不做迁移 = 重建库），故不在本 Task 的范围内；
   本 Task 的处置是把这件事写进 `catalog.py` 那一行的注释与
   `assessment.py` 的模块 docstring，并让反向守卫钉住「它今天真的没有 409 这一档」。
3. **`PATCH {"sex": null}` 会通过 schema 校验、落到 DB 的 NOT NULL 上，得到 409 而不是 422。**
   成因是 `one_of` 一律放行 `None`（`*Update` 的每个字段都是 `X | None = None`，
   而 PATCH 的语义要求「没传」可表达）。要修得给每个 NOT NULL 列另写一个
   「显式 null 也算错」的校验器 —— 那是 41 个模型 × 若干列的活，原型不划算。
4. **list 端点没有 `response_model`**（见 ⑥.2 第 4 条）。Plan 04 若要强类型的 list 响应，
   正解是给工厂加一个「按 `list_exclude` 从 `read` 派生的精简模型」（`pydantic.create_model`），
   不是给 23 个资源各手写一个 `*ListRead`。
5. **`mini_test.entered_by` 与 `notification.recipient_id` 不是外键**
   （前者存教师**工号字符串**，后者是多态的），故 `restrict` 的子行检查**看不到**那两层关系：
   删教师不会挡住他录的小测、删学生不会挡住他的通知。
   两处都在 DB 侧的列注释里登记过，本 Task 只在 `catalog.py` 的对应行重申。
6. **`_purge_where` 的深度 ≥ 2 递归今天不可达**（见第 ④ 节末）。
7. **`scope` 在 23 行里恒为 `None`**（见 ⑥.2 第 7 条）。⚠️ Task 5 若要
   「学生只能看自己的打卡列表」，那是 **list 端点的过滤**，`ScopeFn` 的签名表达不了 ——
   正解是在特例端点里做，**不是**给本工厂加参数。
8. **`class_session` 的 `rpe_opened` / `rpe_token` 跨列一致性在 DB 与 schema 两侧都没有约束**
   （`rpe_opened=False` 而 `rpe_token` 非空是放行的）。DB 侧那一列的注释已经把它交给写入方，
   本 Task 刻意**不**在 API 层加跨列校验 —— 那等于替
   `app.db.models.feedback.ClassSession` 声明一个它自己没声明的不变量。正主是 Task 5。
9. **刻意不做的一批**（计划的显式决定 + 本 Task 的一条）：软删除、审计日志、
   ETag / `If-Match`、批量端点（`mini_test` 的批量录入是 Task 5 的特例端点）、
   服务端排序参数（⑥.2 第 5 条）。

### ⑥.4 待清扫（**6 条**，全是散文精度，无 Critical）

1. `crud.py` 模块 docstring 那张 23 行对照表里，`/api/stratification-results` 一行
   与表头少一个空格，RST 表格的列宽没对齐（渲染仍正确）。
2. `app/db/session.py` 的模块 docstring 仍写「**15** 张表的模型在 `app.db.models`」，
   `Base` 的 docstring 也写「全部 **15** 张表」—— Plan 01 的旧数，今天是 25。
   ⚠️ **本 Task 没动那个文件**，属前序遗留；`init_db` 函数体里那句
   `# noqa: F401  仅为把 15 张表注册进 Base.metadata` 同病。
3. `app/db/repo.py` 的 `upsert` docstring 写「对 **14** 个模型通用」——
   今天有 25 张表、23 个资源在用它（本 Task 的 POST 就是它的新调用方，
   而且是**第一个 HTTP 侧**的调用方）。
4. `commit ① 的信息`里写「批次 A 12 条」，而 `test_crud.py` 最终是 **31** 条
   （12 + 17 + 2）。commit 信息不追改（它是历史），记在这里免得对不上账。
5. `app/api/schemas/__init__.py` 的布局表里 `_base` 那一行的「只读」列填的是 `—`，
   与其余行的数字列对齐方式不同（那一行不是资源）。
6. `tests/api/test_crud.py` 的 `_seed_one_row_per_table` 是 **24 张表 × 手写字面量**
   （约 300 行）。它今天服务于两条遍历守卫，而 Task 5/7/8 很可能也需要
   「一个每表一行的库」。**若第三个 Task 也要它，就该把它提到 `tests/api/conftest.py`
   当夹具**；本 Task 刻意不提前搬（只有一个用户时搬是猜测）。

---

## ⑦ 最终验收

| 项 | 要求 | 实测 | 判 |
|---|---|---|---|
| `python -m pytest -q` | 845 → ? 且既有 845 条一条不退步 | **876 passed**（845 + 31） | ✅ |
| 带 `--cov` | 844 passed, 1 skipped | **875 passed, 1 skipped** | ✅ |
| `app/domain` 四格 | **逐字不变** 996/0/288/0/100% | **996 / 0 / 288 / 0 / 100%** | ✅ |
| 表数 | 仍 **25** | 25 | ✅ |
| `_MODELS_PUBLIC_BASELINE` | 仍 **33**、常量不动 | 33（`dir()` 公有名 39 = 33 + 6 子模块） | ✅ |
| 扫描面 | 38 → ?（下界断言不改） | **49**（api 3 → 14）；`>= 18` 未改、仍绿 | ✅ |
| 架构守卫 | 全绿 | `tests/architecture` 全绿（3 条） | ✅ |
| 三个指纹 | 逐字不变 | `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` **全部 `同=True`** | ✅ |
| `git diff 40a7a0e HEAD -- backend/data` | 为空 | **空**（`--stat` 无输出） | ✅ |
| `backend/data/seed/` | 0 文件 | 目录存在、`rglob('*')` 计数 **0** | ✅ |
| `backend/data/**/*.yaml` 的 CRLF | 全 0（`read_bytes()` 口径） | 21 个 YAML **全部 CRLF=0** | ✅ |
| `backend/pe.db` | **不得存在** | `Test-Path` → **False** | ✅ |
| `backend/pe_demo.db` | （Task 2 已删；本 Task 未起 uvicorn） | `Test-Path` → **False** | ✅ |
| 工作树 | 干净 | `git status --short` 无输出 | ✅ |
| 全仓 `MUTATION` / `_MUTATED` 残留 | 0 | `Grep` → **No matches found** | ✅ |

**改动面**（`git diff --stat 40a7a0e HEAD`，13 个文件）：

```
backend/app/api/crud.py                  604 行  34 481 B   新建
backend/app/api/schemas/__init__.py       46 行   3 128 B   新建
backend/app/api/schemas/_base.py          69 行   4 140 B   新建（⚠️ File Structure 之外，顶回 1）
backend/app/api/schemas/organisation.py  267 行   9 357 B   新建
backend/app/api/schemas/assessment.py    236 行   9 229 B   新建
backend/app/api/schemas/derived.py        94 行   3 812 B   新建
backend/app/api/schemas/prescription.py  156 行   7 784 B   新建
backend/app/api/schemas/feedback.py      208 行   9 411 B   新建（⚠️ Files 清单之外，顶回 1）
backend/app/api/schemas/alerts.py        135 行   6 910 B   新建（⚠️ 同上）
backend/app/api/routers/__init__.py       33 行   2 060 B   新建
backend/app/api/routers/catalog.py       446 行  21 212 B   新建
backend/tests/api/test_crud.py          1659 行  72 449 B   新建（31 条测试）
backend/app/main.py                      225 行  12 854 B   修改（+13 / −4）
————————————————————————————————————————————————————————
生产代码合计                            2294 行；含测试 4178 行 / 196 827 B
```

行数与字节数一律 `read_bytes()` 口径（硬规矩 #89 的扩写）。
12 个新文件的 `CRLF=0`、`BOM=False`；`main.py` 是 `CRLF=225`（**改前就是 CRLF**，
本 Task 的编辑保持了它原有的行尾，且它不在 `backend/data/**` 下、不受
`.gitattributes` 的 `eol=lf` 约束）。
⚠️ 提交时 git 报了 12 次 `LF will be replaced by CRLF the next time Git touches it`
—— 那是 `core.autocrlf=true` 的正常提示，**索引里存的是 LF**，
故三个被指纹钉住的文件（都在 `backend/data/`、`eol=lf`）不受影响，
上表的指纹复核是在**提交之后**跑的。

**新增测试 31 条**（`tests/api/test_crud.py`）：

* 批次 A（12）：`test_list_returns_items_total_limit_offset`、`test_limit_over_200_is_422`、
  `test_offset_beyond_total_returns_empty_items`、`test_create_returns_201_with_a_location_header`、
  `test_create_with_a_duplicate_natural_key_is_409`、`test_read_one_returns_the_row`、
  `test_read_a_missing_pk_is_404`、`test_patch_changes_only_the_keys_present`、
  `test_delete_returns_204_and_the_row_is_gone`、
  `test_a_readonly_resource_rejects_post_patch_delete_with_405`、
  `test_a_forbidden_delete_is_405_even_on_a_writable_resource`、
  `test_list_omits_the_big_json_columns_but_read_one_includes_them`
* 批次 B（17）：`test_all_twenty_three_resources_are_listable`、
  `test_the_read_write_matrix_counts_are_pinned`、
  `test_every_resource_declares_on_delete_explicitly`、
  `test_the_factory_rejects_a_bad_configuration`、
  `test_the_eleven_non_public_models_are_reached_through_their_submodules`、
  `test_every_resource_path_is_a_hyphenated_plural_under_api`、
  `test_every_read_schema_covers_exactly_the_model_columns`、
  `test_natural_key_is_a_real_unique_constraint_of_that_table`、
  `test_every_resource_list_omits_json_text_columns_and_read_one_includes_them`、
  `test_child_tables_skips_the_foreign_keys_that_clear_themselves`、
  `test_a_conflict_message_names_the_key_columns_and_never_the_literal_none`、
  `test_a_resource_without_a_natural_key_never_returns_409`、
  `test_on_delete_restrict_names_the_blocking_child_table`、
  `test_on_delete_cascade_deletes_children_first`、
  `test_the_scope_hook_rejects_a_mismatched_identity_with_403`、
  `test_a_value_outside_the_model_domain_is_422_not_409`、
  `test_every_table_has_a_single_column_primary_key`
* 批次 C（2）：`test_readable_false_turns_off_both_get_endpoints`、
  `test_an_explicit_list_exclude_overrides_the_auto_detection`

**变异自证 3 条**（Ruling 1 说变异只在 Task 6 要求；Task 2 的实现者自己加了一条、控制者采纳并鼓励。
三条都是「改一处 → 跑对应的测试 → 看它红 → 还原」，全仓已复核零残留）：

| # | 变异 | 变红的测试 | 报出来的形状 |
|--:|---|---|---|
| ① | `_child_tables_of` 的 `in _SELF_CLEARING_ONDELETE` → `in frozenset()` | `test_child_tables_skips_the_foreign_keys_that_clear_themselves` | `assert [('notification','alert_id')] == []` —— 正是 P3-B4 预言的那句假话 |
| ② | `list_exclude` 的自动探测 → `()` | `test_list_omits_the_big_json_columns_but_read_one_includes_them` **与** `test_every_resource_list_omits_json_text_columns_and_read_one_includes_them`（两条一起红） | `assert 'input_snapshot' not in {...}` / `('/api/interest-surveys', 'dimensions')` |
| ③ | PATCH 的 `exclude_unset=True` → `False` | `test_patch_changes_only_the_keys_present` | `409 NOT NULL constraint failed: student.student_no` —— ⚠️ 在**可空**列上（如 `department`）同一变异是**静默清空**，这正是那条测试第一拍存在的理由 |

---

## ⑧ commit sha

| sha | 一句话 |
|---|---|
| `51b5b19` | ① 泛型 CRUD 工厂 `build_crud_router` + `schemas/{__init__,_base,organisation,derived}` + `routers/{__init__,catalog}`（4 个资源）+ `main.py` include + 批次 A 的 12 条测试（845 → 857 passed） |
| `dabc3ef` | ② 余下 4 个 schema 模块（`assessment` / `prescription` / `feedback` / `alerts`），41 个模型字段集与 DB 列集逐字对齐（探针实测） |
| `7fa8ecf` | ③ `catalog.py` 扩到 23 行 `RESOURCES` + 批次 B 的 17 条遍历型守卫（含顶回 2/3 的完整逐行清单）（857 → 874 passed） |
| `9a62a93` | ④ 收尾：`upsert` 回滚守卫 + `readable` / `list_exclude` 显式覆盖两条守卫（874 → **876 passed**） |

**没有 push、没有切分支、没有碰 main。**
