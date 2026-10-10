# Plan 03 全分支终审 · fix 波实现者报告

> 分支 `fix/plan-03-review-findings`（从 `main` 的 `20797e7` 起）。**没有 push、没有碰 main**。
> 派单要求一次性修完 6 条：C1（Critical，用户裁定选 A）、写入侧加强制（用户裁定）、I4、I1、I2、I3。**6 条全部落地**；M2 顺手修了；M1 / M3 按派单**不在本波修**。

---

## ① 环境与基线复现

硬规矩 #73 的第一件事：

```
$ python -c "import sqlalchemy, fastapi, uvicorn, httpx, pydantic, yaml; print(sqlalchemy.__version__, fastapi.__version__)"
2.1.3 0.141.1
```

没有出现 `ImportError: DLL load failed`（Smart App Control 没有拦 `.pyd`），故全程正常开工。环境：Python 3.11.1、**无 venv**、SQLAlchemy **2.1.3**、FastAPI **0.141.1**、Starlette 1.7.0、Pydantic 2.13.5、uvicorn 0.54.0、httpx 0.28.1、PyYAML 6.0.3。

**开工前的基线（`20797e7`，工作树干净）逐个复现：**

| 格 | 派单给的 | 本波实测 | 对上了吗 |
|---|---|---|---|
| `python -m pytest -q` | 1244 passed | **1244 passed**（151.56 s） | ✅ |
| `--cov=app.domain --cov-branch` | 1268 / Miss 0 / 376 / BrPart 0 / 100% | **1268 / 0 / 376 / 0 / 100%** | ✅ |
| 带 `--cov` 的 passed | 1243 passed, 1 skipped | **1243 passed, 1 skipped** | ✅ |
| 表 | 25 | **25** | ✅ |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33**（本波一个字没动 `app/db/models/`） | ✅ |
| 扫描面 | 60 | **60**（pipeline 10 + db 11 + domain 18 + api 21） | ✅ |
| `/api/` 路径模板 / 操作 | 63 / 91 | **63 / 91** | ✅ |
| 黄金用例 | 14 | **14**（`test_golden_cases.py` 收到 19 条，其中参数化的是 `[0-GC01]` … `[13-GC14]`） | ✅ |
| 挂 `security` 的操作 | 18 | **18** | ✅ |
| mutating 操作 | 35（9 带 security / 26 不带） | **35 / 9 / 26** | ✅ |
| 2xx 带 schema | 终审更正为 **83/91** | **83/91** | ✅（M1 那个数确认） |
| `securitySchemes` | 2 格 | **2 格** | ✅ |
| `len(app.routes)` | 5–6（假绿口径） | **6** | ✅ |

⚠️ 端点计数**一律用 `app.openapi()["paths"]`**。本机亲验那个假绿：`len(app.routes) == 6`，其中只有 **1** 个 `_IncludedRouter` 节点、它的 `original_router.routes` 展开也只有 6 条（因为 `api_router` 自己又是一层嵌套的折叠节点）——**要拿到真路由必须递归展开**，只展开一层仍然数不全。这一格已写进 `app/api/routers/__init__.py` 的新注释（见第 ④ 节 I3）。

---

## ② C1（Critical，用户裁定选 A）：一处方一周至多减一次

### 2.1 先复现终审那个数

在**未修**的 `20797e7` 上，用 `tests/pipeline/test_alert_stage.py` 的夹具（探针 `$env:TEMP/pe_probe/p4_factor.py`，不在仓库里）造「同一个学生同一处方周同时命中两条红色规则」：

```
adjustments_written = 2
weekly_adjustment rows = 2
   week 3 factor 0.8 reason RED_MINITEST_DROP  source auto
   week 3 factor 0.8 reason RED_RPE_SUSTAINED  source auto
week-3 sheet factor = 0.6400000000000001
reasons = ('RED_MINITEST_DROP', 'RED_RPE_SUSTAINED') sources = ('auto', 'auto')
```

与终审两次独立复现的那个数**逐字相同**（含浮点尾数）。⚠️ `reason` 记的是 `RED_MINITEST_DROP` 而不是 `RED_RPE_SUSTAINED`：`RuleId` 的**声明序**里 `RED_MINITEST_DROP` 在前（spec §8.2 表格行序），而 `evaluate_student` 按声明序返回 —— 故「第一条命中的规则」是它。

### 2.2 落地：那道 SELECT（`app/pipeline/alert_stage.py`）

新增一个**有名字的**私有函数（而不是把 5 行 SELECT 内联进 `_write_auto_adjustment`）：

```python
def _auto_adjustment_exists(session: Session, prescription_id: int, week: int) -> bool:
    return session.scalar(
        select(WeeklyAdjustment.id).where(
            WeeklyAdjustment.prescription_id == prescription_id,
            WeeklyAdjustment.week == week,
            WeeklyAdjustment.source == AUTO_SOURCE,
        )
    ) is not None
```

调用点在 `_write_auto_adjustment` 的 `try:` 里、`session.flush()` **之前**：

```python
    try:
        if _auto_adjustment_exists(session, prescription.id, week):
            logger.info("处方 %s 第 %s 周已经有一条 %s 调整（来自另一条规则）…", …)
            return False
        session.flush()          # ← 原有的那句承重 flush，位置未动
        with session.begin_nested():
            session.add(WeeklyAdjustment(…))
            session.flush()
    except IntegrityError as exc:  # ← 原有的第二道，**完整保留**
        …
        return False
```

四个刻意的取舍，逐个交代：

1. **键里不含 `reason`** —— 这正是它与 `uq_weekly_adjustment_prescription_week_reason_source`（第三道）的差别，也是它存在的全部理由。
2. **没有改用 `repo.upsert`** —— 它撞键会走更新分支、静默改掉已有行的 `created_at`，而那是 `weekly_factors_of` 的排序键（`ORDER BY created_at, id`）。
3. **保留了 SAVEPOINT + `except IntegrityError` 那一层** —— 它退居**并发的第二道防线**。`_auto_adjustment_exists` 的 docstring 逐字写了它**守不住什么**（硬规矩 #39）：SELECT 与 INSERT 之间那一小段窗口。⚠️ 于是「两条不同规则 + 真并发」这一格**今天没有裁判**，它需要一个 `(prescription_id, week, source)` 的**部分唯一索引**（`WHERE source='auto'`），而那是一次 DDL 变更（本仓不做迁移、25 张表的形状由 Plan 02 钉住）。已登记为关切（第 ⑦ 节）。
4. **SELECT 排在 `try` 里面** —— 它会触发 autoflush，而 autoflush 撞出的 `IntegrityError`因此与 INSERT 撞出的走同一档处置，不会冒泡到 `run_daily` 把整批掀掉。

⚠️ 提成一个函数还有一个**测试面**的理由：单进程里「同一条规则重复触发」如今被这道 SELECT挡在 INSERT 之前，于是既有那条`test_a_duplicate_auto_adjustment_is_rejected_by_the_db_not_silently_updated`**到不了** `IntegrityError` —— 它测的会变成 SELECT，而名字里那句「by the db」成了假绿。故那条测试现在 `monkeypatch.setattr(stage, "_auto_adjustment_exists", lambda *a, **k: False)`来**模拟一次并发**（两个进程同时 SELECT、都没看见对方），于是第三道闸门仍然真的被测到、也仍然真的被需要。

### 2.3 落地：教师端那句文案改成从库里实读（`app/api/routers/alerts.py`）

改前：`f"把本周的训练量减了 {int(round((1.0 - AUTO_REDUCTION_FACTOR) * 100))}%"` —— 从**常量**反推。改后走生产读侧那**同一条链**：

```python
sheet = weekly_training_sheet(
    effective_package(prescription, exercises=exercises()),
    week,
    weekly_factors_of(session, prescription.id),
)
…  body=(f"老师看过你的预警（{row.rule_id}）之后给本周减了量："
        f"本周训练单的系数是 {sheet.factor:.2f}"
        f"（= 骨架 × 本周全部微调的连乘，相当于减了 "
        f"{int(round((1.0 - sheet.factor) * 100))}%）。…")
```

⚠️ 它排在 `_write_auto_adjustment` **之后**（那一次写入要先进 `weekly_factors_of` 的结果）。`AUTO_REDUCTION_FACTOR` 在本模块因此不再被用到，已从 import 里去掉（`AUTO_SOURCE` 仍在）。
⚠️ **标题刻意仍是字面量** `"本周训练量已减 20%"`：它说的是教师**这一次点击**做的事（spec §8.4 的「减量 20%」= `ACTION_REDUCE` 那一档的名字），而正文那个系数说的是**这一周的训练单现在实际是多少**。两者不是一件事；且它被`tests/api/test_end_to_end.py` 的 `REDUCTION_TITLE` 字面钉住（两侧不同源，硬规矩 #35）。

### 2.4 落地：「三道闸门」→「四道闸门」

`app/pipeline/alert_stage.py` 的模块 docstring 那一节改成了**四道**，并逐字写明分工：**前三道挡「同一条规则重复触发」，第四道挡「两条不同规则同周」**，两者不重叠。同时在失效形态那一节补了「它还有**第二种进来的路**」一段（点名 `0.6400000000000001` 与 spec §8.4 的「减量 20%」）。`_write_auto_adjustment` 的「三个决定」也改成「四个决定」，第 3 条补了「退居并发的第二道防线、但**不要因此删掉它**」及其失效形态。

`app/domain/prescription/weekly.py` 里 `weekly_training_sheet` 那段散文按选 A 改写：

> ⚠️⚠️ **「相乘」今天只对 `source='teacher'` 与 `source='auto'` 并存这一种情况成立** …
> * **`auto` 自己不叠加** … 于是 `sources` 里**至多一个** `"auto"`。
> * **`teacher` 与 `auto` 并存时仍然相乘** …

并如实补了一句（硬规矩 #39）：`"teacher"` 这个值**今天没有生产写入方**（教师端那个「减量 20%」写的是 `"auto"`，而教师覆盖走 `prescription.teacher_overrides`那一列、不是本表），故那一格今天只在测试里可达。**见第 ⑦ 节的顶回 1。**

### 2.5 守卫（3 处）

| 守卫 | 住址 | 钉什么 |
|---|---|---|
| `test_two_different_red_rules_in_the_same_week_reduce_once_not_twice` | `tests/pipeline/test_alert_stage.py`（新增） | 四格：① `adjustments_written == 1`；② `weekly_adjustment` 只有一行、`reason` 是 `RED_MINITEST_DROP`、`week == 3`；③ 走生产读侧那条链（`effective_package` → `weekly_factors_of` → `weekly_training_sheet`）得到 `sheet.factor == 0.8`；④ `alert` 表里两条红色预警**都在**（另有一条 `YELLOW_CHECKIN_GAP`，字面写死成三元素清单） |
| `test_a_duplicate_auto_adjustment_is_rejected_by_the_db_not_silently_updated` | 同上（改造） | 加 `monkeypatch` 把第四道置成恒 `False` 来**模拟并发**，于是第三道（SAVEPOINT + `IntegrityError`）仍然真的被测到 |
| `test_the_whole_loop_runs_over_real_http` 的 **③bis** | `tests/api/test_end_to_end.py`（扩） | 端到端那一格从「一条红色」扩到「两条红色同周」 |

**端到端那条怎么扩的**（派单第 2 节第 4 点最后一格）：新增 `_seed_a_minitest_drop()`，直接落三行 `mini_test`（`normalized_score` 100 → 90 → 80）。⚠️ **这一步不走 HTTP，是本文件唯一一处例外**，理由逐字写在它的 docstring 里：`mini_test.normalized_score` 那一列**没有任何 HTTP 写入方**（`POST /api/mini-tests/batch` 逐字把它留成 `NULL`，真算法住在读侧的`GET /api/mini-tests/normalized`，而 `alert_stage._student_signals` 读的是**那一列里现有的值**），故走 HTTP 录入的小测喂不进 `RED_MINITEST_DROP`。`batch_id` 留 `NULL` → 天然躲过 `_replay_cleanup`。

连带改的既有断言（硬规矩 #88：先跑全量、把红掉的逐个收进来）：

* ④ `alert_count` **2 → 3**（学生级 `RED_MINITEST_DROP` + 学生级 `RED_RPE_SUSTAINED` + 班级级 `YELLOW_CLASS_RPE_HIGH`）；⑤ `total` **2 → 3**，并新增「`RED_MINITEST_DROP` 恰好一条」；
* ⑥ 新增一格：**推送正文里含 `0.80`** —— 它把「文案从库里实读」这件事也钉住了（下面的变异取证里，正是这一格先红，并报出了 `0.64` / `36%`）；
* ⑦ `sheet["reasons"]` 从 `["RED_RPE_SUSTAINED"]` 改成 `["RED_MINITEST_DROP"]`（`factor == 0.8` 那一句不动）；
* ⑥ 那一段的注释按实际改写：`adjustment is None` 如今**不是**「撞上四列唯一约束」，而是被那道不含 `reason` 的 SELECT 挡下 —— 两行的 `reason` 不同，那个约束**拦不住**。

### 2.6 变异取证（硬规矩 #83，三重还原）

变异：把 `_write_auto_adjustment` 里那道 `if _auto_adjustment_exists(…): … return False`**整块删掉**（734 字节），改完清 `__pycache__`（21 个目录）。

| | 变异态 | 还原后 |
|---|---|---|
| `adjustments_written` | **2** | 1 |
| `weekly_adjustment` 行数 | **2**（`RED_MINITEST_DROP` + `RED_RPE_SUSTAINED`） | 1 |
| 第 3 周训练单 `factor` | **0.6400000000000001** | **0.8** |
| 新单元测试 | **红**（`assert 2 == 1`） | 绿 |
| 端到端 ③bis 那条 | **红**，且报错逐字是：`实际正文是 '…本周训练单的系数是 0.64（… 相当于减了 36%）…'` | 绿 |
| `alert` 表 | 3 行（两条红 + 一条 `YELLOW_CHECKIN_GAP`） | 3 行（**可追溯性不丢**） |

**三重还原证据：**

1. **sha256 复原**：`alert_stage.py` 变异前 = 还原后 = `25399a5eec2eb212ecd1f64a9583d383dc91d8cf457df9b4167973611a97b47b`（`MATCH = True`）；
2. **`git diff` 复原**：`git diff --stat -- backend/app/pipeline/alert_stage.py` 变异前后逐字相同（`94 insertions(+), 2 deletions(-)`）；
3. **复跑全绿**：`tests/pipeline/test_alert_stage.py` 37 passed；`tests/api` 180 passed；全量 **1251 passed**。

### 2.7 官方演示库上那一个重复减量也消失了

终审说演示库上 10 个受影响（处方，周）里有 **1** 个带两条 auto 调整（`prescription_id=11 week=1`）。修完之后：`weekly_adjustment` **11 → 10 行**，而 `alert` 从 11 → **30** 条（那是 I2 让 `GREEN_MASTERY` / `YELLOW_CHECKIN_GAP`也触发起来的连带，见第 ⑥ 节）。

---

## ③ 写入侧加强制（用户裁定：8 个可写资源都要教师头）

### 3.1 可写资源**实测是 9 个**，不是 8 个

按硬规矩 #44 自己数（`RESOURCES` 里 `"writable": True` 的行数 + 一条守卫钉住）：

```
/api/semesters             on_delete=forbid     ← 没有 DELETE 端点
/api/teachers              on_delete=restrict
/api/students              on_delete=restrict
/api/course-sections       on_delete=restrict   natural_key=None
/api/enrollments           on_delete=restrict
/api/fitness-test-batches  on_delete=restrict   natural_key=None   ← 派单那 8 个名字里漏的就是它
/api/body-compositions     on_delete=restrict
/api/interest-surveys      on_delete=restrict
/api/class-sessions        on_delete=cascade
```

与 `tests/api/test_crud.py::test_the_read_write_matrix_counts_are_pinned` 里那份**字面清单**逐字对上了（那一条早就写着「可写 9 / 只读 14」，是 Plan 03 Task 3 顶回简报的一处）。故 26 = 9 POST + 9 PATCH + **8** DELETE。

### 3.2 `build_crud_router` 的新参数：`require_teacher`

```python
def build_crud_router(*, model, schemas, path, tags, pk="id", pk_alias=None,
                      order_by="id", readable=True, writable=True,
                      require_teacher: bool = False,      # ← 新
                      on_delete=ON_DELETE_RESTRICT, natural_key, …) -> APIRouter:
```

`True` 时给 **POST / PATCH / DELETE** 三个端点挂
`dependencies=[Security(TEACHER_STAFF_NO_SCHEME), Depends(_require_teacher_identity)]`；**GET 一个都不挂**（大屏与列表要能匿名读，Task 3 的偏离 ⑦「身份头条件注册」不变）。

新增的 `_require_teacher_identity` 是 `deps.current_teacher`（缺头 **401**）与`deps.require_teacher`（工号在册 **403**）的**组合**，两个判定都不重写。它的 docstring 逐字交代了为什么 `Security(...)` 与它**必须成对挂**：只挂前者 = 「spec 上写了、实际谁都放行」（`TEACHER_STAFF_NO_SCHEME` 是`auto_error=False`，缺头**不**抛）；只挂后者 = 「前端从 spec 上看不出来要带头、一接就 401」（P4-A5 当初要修的那个缺口）。

⚠️ 另加**第 7 道**配置校验：`require_teacher=True` 与 `writable=False` 互斥（只读资源根本不注册那三个端点，挂上去是一件什么也不发生的事，失效形态是静默的）→ 导入期 `ValueError`。`test_the_factory_rejects_a_bad_configuration` 从「六道」改成「七道」。

### 3.3 「挂 `security` 的操作数」：18 → **44**

| 格 | 修前 | 修后 |
|---|---|---|
| `/api/` 路径模板 | 63 | **63** |
| 操作 | 91 | **91** |
| 挂 `security` 的操作 | 18 | **44**（18 特例 + 26 CRUD 写入） |
| mutating 操作 | 35（9 带 / **26 不带**） | 35（**35 带 / 0 不带**） |
| `components.securitySchemes` | 2 格 | **2 格**（没新增第三个 scheme） |
| spec 顶层 `security` | `None` | **`None`** |
| 2xx 带 schema | 83/91 | **83/91** |

### 3.4 遍历型守卫（2 条新增，都在 `tests/api/test_crud.py`）

* **`test_every_writable_resource_declares_require_teacher_explicitly`** —— 断言**键在不在**（缺省值不算显式，与既有 `on_delete` 那条同一条纪律），9 个可写资源的清单**字面写死**，并反向钉「只读的 14 行不该出现这个键」。
* **`test_every_writable_resource_rejects_an_anonymous_mutation`** —— 遍历 `RESOURCES`：
  * 可写的：**实发**不带头的 POST / PATCH / DELETE → **401** 且 `error.code == "unauthenticated"`；`on_delete=forbid` 的那一个 DELETE 断 **405**；同时逐个断 OpenAPI 上 `security == [{"X-Teacher-Staff-No": []}]`；再断两个 `GET` 仍 **200 且不带 `security`**（两侧都在场，硬规矩 #50）；
  * 只读的：POST / PATCH / DELETE 仍 **405**，且 `paths` 里根本没有那些方法。
  * 末尾钉 `checked == {"post": 9, "patch": 9, "delete": 8}`（本条会在 `RESOURCES` 被写空时空转全绿）。

⚠️ **被测面一律走 `app.openapi()["paths"]` 与实发请求，绝不走 `app.routes`**（理由与实测逐字写在它的 docstring 第二节）。

⚠️ 途中实测到的一条**例外**，已字面写死成 `_STUDENT_OWNED_POSTS`：只读的 14 个里有 **2 个**（`/api/rpe-records`、`/api/training-logs`）的 POST **不是 405**而是 **401** —— 那两个 POST 不是泛型工厂注册的，是 `app.api.routers.feedback` 的两个**学生侧特例**端点（挂 `Security(STUDENT_ID_SCHEME)`）。派单说的「对每个 `writable=False` 的资源断言仍是 405」因此对这两个路径**不成立**，守卫里把它们列成显式例外并断它们的 `security` 是学生那一格。

⚠️ 另一条实测事实（已写进 `test_a_value_outside_the_model_domain_is_422_not_409` 的注释）：**依赖跑在请求体校验之前** —— 不带头时 `POST` 一个空 body 得到的是 **401** 而不是 422。这既是遍历型守卫能用 `json={}` 一把梭的原因，也意味着那条 422 的测试**必须**带头。

### 3.5 `test_prescription_api.py` 那条全仓级断言改成了什么

`test_the_identity_headers_are_registered_as_openapi_security_schemes` 的第 ③ 拍：

* **改前**：`assert [(k, m) for k, m in crud if paths[k][m].get("security")] == []` —— 逐字是「23 个 CRUD 资源的端点一个都不带 `security`：它们不要求身份，而 OpenAPI 上多出来的要求会让前端以为每个 CRUD 都要登录」。
* **改后**（新口径 = 「可写的 9 个带 `security`、只读的 14 个不带」）：
  1. 读的一侧：`crud` 里所有 `get` 一个都不带 `security`；
  2. 写的一侧：`got_crud_security == expected_crud_security`（期望侧由**字面**的 9 个可写路径 × `post/patch/delete` 减去 `semesters` 的 DELETE 现拼，并断 `len(...) == 26`），且每一个的 `security` 逐字等于 `[{"X-Teacher-Staff-No": []}]`；
  3. 全仓合计：`len(all_security) == 44`，并配一句 `len(expected) == 18`（特例清单不是 18 项时，44 那个算式要跟着改）。
* **docstring 逐字写明了为什么口径变了**：不是「口径漂了」，而是那句话描述的现状本身是个洞（终审实测的 26 个匿名 mutating 操作 + 四个连着 201 的 POST）；并把「`catalog` 那 23 个资源一个 `Security` 都不挂、故真正声明的是**五个**」那半句标注为**已过期**（现在六个 router 全都声明）。用户裁定日期 2026-10-08 写进去了。

### 3.6 变异取证（两次，三重还原）

| 变异 | `test_every_writable_resource_rejects_an_anonymous_mutation` | `test_the_identity_headers_…security_schemes` |
|---|---|---|
| ① `if require_teacher:` → `if False:`（整个闸门关掉） | **红**（`POST /api/semesters` 变 **422**，即请求体校验先命中） | **红**（少了 26 项） |
| ② 只留 `Security(...)` 声明、删掉 `Depends(_require_teacher_identity)` | **红**（同上 422） | **绿** ← 正是「spec 上写了、实际谁都放行」那一档，**只有行为面能抓到** |

还原：`app/api/crud.py` sha256 = `20db998f9ed706d0bb9e4503e6e82677d3f2a9bde6e6490c238aa8401515e637`（两次 `MATCH = True`），`git diff --stat` 复原为 `87 insertions(+), 5 deletions(-)`，复跑全量 **1251 passed**。

### 3.7 收进来的既有测试（硬规矩 #88）

全量跑一次红了 **11** 条，逐个收：`tests/api/test_crud.py` 的 **10** 条（对可写资源的写请求补上新夹具 `teacher_headers`）+ `test_prescription_api.py` 的 **1** 条（上面 3.5 那条）。`teacher_headers` 夹具**真的插一行在册教师**（否则拿到的是 403 而不是 201），工号刻意用 `T2025900` 而不是 `_seed_one_row_per_table`那个 `T2025001` —— 两个夹具的先后由测试签名的形参顺序决定，用同一个工号会让`seeded` 当场撞 `teacher.staff_no` 的唯一约束。

`tests/api/test_end_to_end.py` **一条都没红**：它的 ③ 早就带 `headers_teacher`。

---

## ④ I4 与 I3

### 4.1 I4：`rpe_token` 从泛型 `class-sessions` 的写侧**摘掉**（不是加 validator）

派单给了两个选项，取**去掉字段**，因为「加 `field_validator` 强制长度」治不了真病：长度只是 `_new_rpe_token()` 那两个不变量之一（另一个是 CSPRNG），而客户端自己挑的口令**即使长度对**也仍然是「教师端的第一个按钮被指向了一扇绕过`open-rpe` 的门」。且去掉字段与 Task 4 的 `OverrideCreate` 少两格、Task 5 的`RpeSubmitCreate` 少两格是**同一条纪律**（服务端填的列不上请求模型）。

实测确认「去掉字段不破坏什么」：`rpe_token` 的写入方今天有三个 —— `app/demo_data.py`（走 `repo.upsert`，**不经 schema**，不受影响）、`open_rpe`（正主）、泛型 POST/PATCH（本波摘掉）。`ClassSessionRead` **仍含**那一列（`*Read` 与 DB 列逐字对齐是既有守卫的口径）。

落地：

* `ClassSessionCreate` / `ClassSessionUpdate` 各去掉 `rpe_token`（6 列 → **5** 列）；
* `ClassSessionUpdate` 那句过期 docstring 改成指向 `POST /api/class-sessions/{class_session_id}/open-rpe`，并把「前后两句互相矛盾」这件事**逐字写进新 docstring**（免得下一个人以为这次改写是随手润色）；
* `app/api/routers/feedback.py` 的 `open_rpe` docstring 里那句「但泛型的 PATCH 仍然能把两列改成不一致，故那条关切只算兑了一半」按实际改写：它现在是那一列**唯一**的 API 写入方；剩下的半格是「泛型 PATCH 仍能把 `rpe_opened`单独翻上去」，而 `submit_rpe` 对那一档报 **409 `rpe_not_opened`**—— 一个**安全的失败**，不是一句谎；
* ⚠️ `rpe_opened` **刻意留在**两个模型上（教师可以先建课次、稍后再发起快评），代价如实记录。

收进来的既有断言（1 条）：`test_every_read_schema_covers_exactly_the_model_columns`钉的是「`*Create`/`*Update` 的字段集 = 全部列减去 `id`」，去掉一列会当场红。改成减去一份新的**字面清单** `_SERVER_FILLED_COLUMNS`（今天一格：`{"/api/class-sessions": ("rpe_token",)}`），并**反向**也钉：清单里点名的列必须①真的是该表的一列、②真的**不在**那两个模型上（少了②，「把一列写进清单来绕过对齐断言」就成了什么也不做的改动）。`counted` 仍是 **41**（23 read + 9 create + 9 update）。
另：`test_on_delete_cascade_deletes_children_first` 的 POST body 上那个`"rpe_token": "ZZZ99999"` 删掉了（它现在会被 Pydantic 静默丢掉，留着等于一行「看起来在写它而其实没有」的谎）。

### 4.2 I3：那句警告搬进纪律的住址

`app/api/routers/__init__.py`（「特例一律在 `catalog` 之前 include」的住址）新增一段 `⚠️⚠️⚠️ **写路由顺序守卫之前必读：不要用 app.routes**`，内容包含：

* 本机实测：`len(app.routes) == 6`（4 个内置 + `/api/health` + **1** 个 `_IncludedRouter`）；
* 终审那条结论逐字抄进来：按 `app.routes` 写的遮蔽扫描**在今天正确的顺序上**与**在一个把顺序排反的最小 app 上**都报「0 对遮蔽」——一条两种情况都报同一个数的守卫等于没有守卫；
* **两个可用口径及各自的局限**（硬规矩 #103）：① `app.openapi()["paths"]`（首选、完整，但它答「注册了什么」、**答不了「谁先匹配」**）；② 递归展开 `_IncludedRouter.original_router.routes`（保序、能拿到真 `APIRoute`，但是**私有类型**，故用它写的守卫必须先断言「展开出来的路由数 > `len(app.routes)`」，否则它会静默退化成上面那个假绿）；
* 本仓的既定形状因此是「**实发请求**」，并点名那个 422 为什么阴险（它会把下一个人支去修前端传的参）。

**顺手把清单式守卫写了**（派单说「若你顺手写了，更好」）：`tests/api/test_feedback.py` 新增`test_every_literal_tailed_special_route_beats_the_generic_placeholder_route`，期望侧是字面写死的 `_LITERAL_TAILED_SPECIAL_ROUTES`（3 个：`mini-tests/batch`、`mini-tests/normalized`、`pipeline/run-daily`）。⚠️ 它**不是**笼统断「!= 422」，三条各用一种「只有命中特例端点才可能得到」的证据：`batch` 断响应体逐字等于`{"created": 0, "failed": []}`；`normalized` 断 `sections` 那一格；`run-daily` 断 422 的 `loc` 里有 `("body", "business_date")`（那个键只存在于 `RunDailyCreate` 上）**且没有任何 `loc` 的第一段是 `"path"`**。docstring 如实写明：3 个里今天**只有 `normalized` 真的与泛型同形**，另两个是「将来谁把 `mini-tests` 改成可写、或加一个叫 `pipelines` 的资源」时的绊网。

**变异取证**：把 include 顺序排反（`feedback` 挪到 `catalog` 之后）→ 新的清单式守卫与既有的点状守卫**一起红**，报错逐字是终审预言的那一句：`{"type":"int_parsing","loc":["path","mini_test_id"],"input":"normalized"}`。还原后 sha256 = `0853d226f33984744e6a540bc29a515c581657998621656907d0a8d1aa204b27`（`MATCH = True`），复跑 `tests/api/test_feedback.py` 47 passed。

---

## ⑤ I1：`run_daily` 的 `now` 可注入

### 5.1 新签名

```python
def run_daily(
    session: Session,
    semester_id: int,
    business_date: str,
    adapter: DataSourceAdapter,
    *,
    now: dt.datetime | None = None,      # ← 新
) -> models.DailySyncRun:
```

**缺省仍是 `dt.datetime.now()`**（函数体里 `if now is None: now = dt.datetime.now()`，位置就是原来那一行，故那 4 个时刻列仍然同源），既有调用方**零改动**：`tests/` 的夹具与 `app/api/routers/pipeline.py` 都不传它。

新增 `app.pipeline.daily.business_now(business_date)` —— 把一个业务日期折成「那一天批处理的业务时刻」= **当天 `00:00`（naive）**，进了 `__all__`。取 `00:00` 的理由写在 docstring 里：报表窗口是`[combine(week_start, time.min), combine(watermark + 1 天, time.min))`，两端都是午夜，故当天 00:00 **恒在窗口内**（含 `as_of == week_start` 与`as_of == watermark` 两个边界日），且它与那个 `dt.time.min` 边界**同源**；取一个更晚的时刻也一样对，但那是个没有收益的自由参数。`str` 那一支走 `parse_business_date`（格式校验的唯一所有者），故一个非法日期在**这里**响、不是在 `combine` 里响。

两个**回放路径**的调用方都传它：

* `app/pipeline/backfill.py`：`run_daily(session, semester_id, day, adapter, now=business_now(day))` —— 每一天注入**它自己**那一天；
* `scripts/demo_bootstrap.py`：两次 `run_daily` 都传 `now=business_now(…)`。

⚠️ `app/api/routers/pipeline.py` 的那个端点**刻意不注入**（生产口径 `as_of == 今天`，两者等价，而真实时刻更有信息量）。**代价如实记录**并写进了 `demo.ps1` 的提示行：演示库的 `as_of` 是历史日，故手工点那一条会把周报的「预警汇总」清零；要重灌请重跑 `demo.ps1`。已登记为关切（第 ⑦ 节）。

### 5.2 `demo_bootstrap.py:229` 那句注释的理由改对了

整段（含那句 `print` 出来的「⚠️ 演示库的 alert_summary 恒为 9 个 0」）**删掉**，换成 `offenders` 的一格 + 逐班实读打印。新注释逐字写明：成因**不是**「演示口径、生产不可达」（那句对 `app.pipeline.backfill` 不成立：回放的语义逐字就是「把一学期的每个业务日都跑一遍」，每一个业务日都是历史日），**真正的原因**是 `now` 此前不可注入。同样的话也写进了 `run_backfill` 的 docstring与 `business_now` 的 docstring（三处指向同一个所有者）。

### 5.3 实测证据：重放一个历史日时 `alert_summary` 的 total **不为 0**

演示库（60 人 / `seed=20250828` / `as_of=2025-10-12`，全部从库里读回来、不是自报）：

```
周报 班 1: 三层完成率 {'red': 0.5,    'yellow': 0.6275, 'green': 0.55}   预警汇总合计 15  建议「维持当前强度」
周报 班 2: 三层完成率 {'red': 0.5625, 'yellow': 0.6944, 'green': 0.6429} 预警汇总合计 15  建议「维持当前强度」
周报 班 3: 三层完成率 {'red': 0.5357, 'yellow': 0.7879, 'green': 0.75}   预警汇总合计 11  建议「维持当前强度」
周报 班 4: 三层完成率 {'red': None,   'yellow': 0.5641, 'green': 0.7857} 预警汇总合计  9  建议「维持当前强度」
周报 班 5: 三层完成率 {'red': None,   'yellow': 0.6,    'green': 0.5}    预警汇总合计 10  建议「维持当前强度」
```

修之前这五格逐字是 `{"red":{"pending":0,…},"yellow":{…0…},"green":{…0…}}`（9 个 0）、`generated_at = 2026-10-10 21:57:25.525775`（真实时钟）；修之后 `generated_at = 2025-10-12 00:00:00`（注入值）、合计 9–15。

### 5.4 守卫（3 条新增）

| 守卫 | 住址 | 钉什么 |
|---|---|---|
| `test_replaying_a_historical_day_lands_the_alerts_inside_the_report_window` | `tests/pipeline/test_daily.py` | 重放 `2025-09-14` + 注入 `business_now(SUNDAY)`：① 全部周报的 `generated_at` 逐字等于注入值；② `alert_summary` 的 **total > 0**（修之前恒为 9 个 0），且同一批里另插一行**窗口外**的（`triggered_at = 注入值 + 30 天`）**不**被算进去（`yellow.pending == 1`）；③ `suggestion == SUGGESTION_REDUCE` —— 那一档在回放路径上**不再结构性不可达** |
| `test_business_now_accepts_both_a_string_and_a_date` | 同上 | 两个入参形状、naive、非法串在这里响；并钉住 `run_daily` 的 `now` 缺省仍是 `None` |
| `test_run_backfill_injects_each_business_day_as_now` | `tests/pipeline/test_backfill.py` | spy 掉 `run_daily`，逐日对拍 `now == business_now(day)`、没有一天是 `None`、且「每一天注入的是它自己那一天」（`len({now}) == len(days)`） |

**变异取证（两次，三重还原）**：① `run_daily` 里 `if now is None:` → `if True:`（忽略注入值）→ 第 1 条守卫红在 `{datetime(2026,…)} == {datetime(2025, 9, 14, 0, 0)}`；② `run_backfill` 不传 `now=` → 第 3 条守卫红（`seen` 里全是 `None`）。两次还原 sha256 分别复原为 `60bd92f7d3e7768fd49258988723863c516d206c5554efc5d5b05ad5e4ca0367` 与 `716a6f7f23ac2ee7bade63eebba68ddf3e9b01df1b3afcae68fa6ffd258854f9`（都 `MATCH = True`），复跑全绿。

---

## ⑥ I2：演示库真的能演示

### 6.1 选了 **(b)**，理由比「(a) 的连带太大」更硬

派单说「控制者倾向 (a)」，本波取 **(b) 让处方生成日早于 `as_of`**。两条**实测出来**的理由（不是「怕麻烦」）：

1. **(a) 结构上离不开 (b) 的那次重排。** `build_demo_feedback` 今天跑在 `run_daily` **之前**，那时库里**一张处方都没有** —— 「按处方的训练日反推」无从反推。故 (a) = (b) 的重排 **+** 再动一次 `demo_data` 的口径，成本严格更高。⚠️ 派单把两者当成互斥的替代方案，这一点不成立（见第 ⑦ 节顶回 2）。
2. **重排之后 (a) 已经没有收益。** 实测 60 张处方的第 1 周训练日模式只有三种，全部从 `generated_on` 起**连续**：

```
# 修之前（generated_on = as_of = 2025-10-12，周日）
('2025-10-12', '2025-10-13', '2025-10-14')                29 张
('2025-10-12', '2025-10-13')                               24 张
('2025-10-12', '2025-10-13', '2025-10-14', '2025-10-15')    7 张
# 修之后（generated_on = 2025-10-06，周一）
('2025-10-06', '2025-10-07', '2025-10-08')                 29 张
('2025-10-06', '2025-10-07')                               24 张
('2025-10-06', '2025-10-07', '2025-10-08', '2025-10-09')    7 张
```

   这与 `training_days_of` docstring 里那句「`AssembledSession.day` 是**周内第几天**（1-based、在一套模板内连续）」逐字吻合。故 `generated_on` 落在**周一**时，训练日就是周一到周三/周四，**一个周末都不含** —— 「按周末判休息日」与「按处方训练日反推」在这一格上给出**同一个答案**。而 (a) 要付的代价是`app/demo_data.py` 那 4 条测试的口径全变（含一条幂等测试「跑三次逐字不变 16/480/1680/480」），换来的是一份**重复的判据**。

### 6.2 落地

`scripts/demo_bootstrap.py` 从 5 步改成 **6 步**，新增 `[3/6] run_daily(DEMO_RX_AS_OF)`：

```
[1/6] write_csv(build_dataset(60 人 / 16 周 / seed=20250828))
[2/6] init_db + seed_database
[3/6] run_daily(2025-10-06)  —— 处方生成日（I2 的第一次；三源还空着，预警应当是 0）
[4/6] build_demo_feedback(as_of=2025-10-12) —— 反馈三源
[5/6] run_daily(2025-10-12)  —— 九个阶段（预警 + 班级周报）
[6/6] 复核（全部从库里数出来，不是自报）
```

`DEMO_RX_AS_OF = rx_as_of_of(DEMO_AS_OF)` = **前 6 天 = 报表周的周一**（偏移的唯一所有者是 `rx_as_of_of()` / `DEMO_RX_OFFSET_DAYS`，`--as-of` 被改过时跟着走）。⚠️ **取 6 而不是 5** 是有原因的、两个约束都写在注释里：

1. `0 <= 偏移 <= 6` —— 否则 `current_week(generated_on, as_of, 4)` 会算出第 2 周（甚至越界返回 `None`），而演示数据只覆盖第 1 周的训练日；
2. `生成日 + {0,1,2,3}` 全是**工作日** —— 偏移 4 会让训练日撞上**周六**、偏移 3 撞上**周日**，那几天被 `demo_data` 标成休息日、被 `_counted_checkin_days` 剔掉；偏移 5（周二起）会让 3 课时的训练日 = 周二/周三/**周四**，而周四恰好是`late = day_offset % 7 == 3` 命中的那一天（`late` 不计入完成率）→ `rate` 上限 2/3、`GREEN_MASTERY`（要 `>= 1.0`）永不触发。**只有偏移 6 让 3 与 4 课时两档都躲开周末与 late 日。**

⚠️ 第二次 `run_daily` 的 `prescription_count` 是 **0**（处方是上一批生成的、这一批一个触发都没命中：分层标签没变、处方也没到期）。那不是失败，故打印改成「本批新生成处方 0 张（处方生成日是 2025-10-06，见 [3/6]）」，复核段另外从库里读回 `generated_on` 的取值集合并打印出来。

### 6.3 演示库上的新实测值（60 人 / `seed=20250828` / `as_of=2025-10-12`）

| 格 | 修前 | 修后 |
|---|---|---|
| `checkin_rate_by_layer`（班 1） | `red 0.0 / yellow 0.0 / green 0.0`（且 `measured == students`，读起来像「测过了、就是 0%」） | `red 0.5 / yellow 0.6275 / green 0.55` |
| 三层全 0 的班 | **5 / 5** | **0 / 5**（班 4、班 5 的 `red` 是 `null` —— 那一层在这个班**没有人**，「不知道」没被讲成「0」） |
| `notification` | **0 行** | **19 行**（`本周电子勋章` 13 + `补练提醒` 6） |
| 出现的规则 | **2** 条（`RED_MINITEST_DROP` 5 / `RED_RPE_SUSTAINED` 6） | **4** 条（`GREEN_MASTERY` 13 / `RED_MINITEST_DROP` 5 / `RED_RPE_SUSTAINED` 6 / `YELLOW_CHECKIN_GAP` 6） |
| `alert` | 11 行 | **30 行** |
| `weekly_adjustment` | 11 行 | **10 行**（C1 的连带：那一个重复减量没了） |
| `alert_summary` | 9 个 0（逐班） | 合计 **9–15**（I1 的连带） |
| 整脚本 `elapsed` | ~1 s | **1.88 s**（`demo.ps1` 的 90 s 哨兵吃得下） |

⚠️ 第 5 条规则 `YELLOW_CLASS_RPE_HIGH` **仍不触发**：演示数据的最高班级均值是 **6.93 < 阈值 7.0**（终审也是这么量的）。那是**数据面**的事、不是本波三条机制的问题，如实记录。要它也触发就得改 `demo_data` 的 RPE 分布（会动它的幂等口径），超出「让演示库真的能演示」的必要范围。

### 6.4 `notification` 为什么是 0 行（查明）+ 现在为什么是 19 行

查明：`InAppChannel` 只在**三条**规则下发消息（`_notify` 的表：`YELLOW_CHECKIN_GAP` → 学生、`GREEN_MASTERY` → 学生、`YELLOW_CLASS_RPE_HIGH` → 教师；两条 `RED_*` **刻意不自动推送**，spec §8.2 逐字「教师点击 → 推送」）。而修前三条**一条都不触发**：`GREEN_MASTERY` 要 `completion_rate >= 1.0` 而它恒 0；`YELLOW_CHECKIN_GAP` 要「连续 2 个**应打卡训练日**未打卡」而窗口里只有 1 个已过的训练日；`YELLOW_CLASS_RPE_HIGH` 是 6.93 < 7.0。故 0 行**不是** channel 坏了，是上游恒 0。修后前两条都触发 → 13 + 6 = 19 行，学生端消息中心与`POST /api/notifications/{id}/read` 因此都可演示。

### 6.5 `offenders` 从 3 格加到 **6 格**

照它既有那几格的形状（当场 `print` 一句人话 + `return 1`）：

4. **三层完成率全是 0/null** → 报警，消息直接指向「处方生成日没有早于 `--as-of`？见模块 docstring 第四节与 `DEMO_RX_OFFSET_DAYS` 的两个约束」；
5. **`notification == 0`** → 报警（学生端消息中心会是空的）；
6. **`weekly_class_report.alert_summary` 全是 0** → 报警（I1 的守卫，消息指向 `app.pipeline.daily.business_now`）。

⚠️ 派单要「两格」，本波加了**三格**：第 6 格是 I1 的**演示侧**守卫（`tests/pipeline/` 那三条钉的是 `run_daily` / `run_backfill`，而 `scripts/demo_bootstrap.py` **没有任何测试文件**，故它自己的复核段是唯一的守卫住址）。实测：`rc = 0`、六格全过。

---

## ⑦ 待清扫 / 关切 / 没按派单做的地方 / 顶回控制者的地方

### 7.1 顶回控制者的地方（**2 处**）

**顶回 1 —— C1 第 2 点给的理由 ① 不成立（理由 ② 成立，改动照做）。**

派单逐字写：「仍要改成从库里实读那一周的乘积，理由：①**教师覆盖（`source='teacher'`）与 auto 可以同周并存，乘积不一定是 0.8**；②让文案与实际 factor 同源」。

**理由 ① 描述的状态今天不可达。** `app/api/routers/alerts.py` 的模块 docstring（「⚠️⚠️ `reduce_20pct` 的 `source` 是 `"auto"`、不是 `"teacher"`」那一节）逐字交代过：教师端那个「减量 20%」写的是 **`"auto"`**，而教师覆盖走的是 `prescription.teacher_overrides` **那一列**、不是 `weekly_adjustment` 表；且 `weekly-adjustments` 这个资源在 CRUD 目录里是 `writable=False`。故 **`weekly_adjustment.source='teacher'` 到今天仍然没有生产写入方**，「teacher 与 auto 同周并存」只在测试里可达。

* **替代方案**：照做（派单说这一条无条件要改，且理由 ② 独立成立 —— 改之前文案从常量推、学生端从 `weekly_training_sheet` 推，是两个各推一遍的量，漂了没有守卫会红）。同时把「今天不可达」这句如实写进`app/domain/prescription/weekly.py` 的新 docstring（硬规矩 #39）。
* **代价**：无。改动本身与理由 ① 是否成立无关。
* ⚠️ 而这一格**恰好被本波另一条改动放大了**：C1 选 A 之后，「同周并存」的唯一来源就只剩 `teacher`，而它没有写入方 —— 故**今天乘积恒为 0.8 或 1.0**。文案改成实读因此暂时看不出差别；它的价值在 Plan 04 给 `weekly_adjustment` 加上 `teacher` 写入方的那一天。

**顶回 2 —— I2 的 (a)/(b) 不是两个互斥的替代方案：(a) 结构上包含 (b)。**

派单把 (a)「按处方的训练日反推」与 (b)「让处方生成日早于 `as_of`」并列成两个方案，并说「控制者倾向 (a)」、(a) 更彻底。

**实测：(a) 无法单独实施。** `build_demo_feedback` 跑在 `run_daily` **之前**，那时库里一张处方都没有 —— 「按处方的训练日反推」没有东西可反推。要 (a) 就必须先做 (b) 的那次重排（先跑一次管道生成处方、再灌打卡、再跑第二次）。而**重排之后 (a) 的边际收益是 0**：18 套模板的 `day` 恒为 `1..N` 连续，`generated_on` 落在周一时训练日就是周一到周三/周四、一个周末都不含，两种判据给出同一个答案。

* **替代方案**：只做 (b)（`demo_bootstrap` 6 步 + `DEMO_RX_OFFSET_DAYS` 的两个约束写进注释 + `offenders` 加格），`app/demo_data.py` **一个字没动**（它那 4 条测试含幂等测试因此全部不受影响，`16/480/1680/480` 那几个数一个都没变）。
* **代价**：`demo.ps1` 多跑一次管道（实测 +~1 s，整脚本 1.88 s；`demo.ps1` 的 `elapsed` 哨兵是 90 s、原实测 43.96/48.37 s，余量足够）；演示库里 `stratification_result` / `derived_metrics` 从**一天**的行变成**两天**（`2025-10-06` 与 `2025-10-12`，⚠️ 两天落在**同一个学期周**里，故 `layer_flow` 的 `has_previous` 仍是 `False`、教师大屏的「周环比流动」仍是空的 —— 模块 docstring 那一段已按实际改写）。
* ⚠️ **本波因此没有顶回「(a) 更彻底」这个价值判断本身** —— 如果 Plan 04 要把演示数据的休息日与处方训练日**严格**对齐（例如以后有模板把 `day` 排成非连续、或 `generated_on` 不再等于某个周一），(a) 仍然是对的方向；本波顶回的是「(a) 与 (b) 二选一」这个**框架**，以及「(a) 成本更低」这个隐含前提。

### 7.2 没按派单做的地方（**3 处**）

1. **I2 选了 (b) 而不是控制者倾向的 (a)** —— 见顶回 2。这是派单**明确授权**的分支（「你若实测发现 (a) 的连带太大，选 (b) 并说明」），故严格说不是偏离；但控制者的倾向没被采纳，故照规矩显式列出来。
2. **M1 的「把账本里那个过期的数改对」没有产生一次账本编辑。** 实测：全仓（`.superpowers/sdd/**` 与 `backend/**`）里 `82/90` **只出现两处**，都是终审自己那句 M1 —— `progress.md:899` 与它的取证脚本 `_final_review.py:75`，而那句本身就逐字写着「**「2xx 带 schema 82/90」这个数已过期** —— 实测 **83/91**」，即**更正已经在原句里**。账本的基线行（`progress.md:851` / `:925`）写的是「63 个路径 / 91 个操作」，**没有**那个过期数；`task-9-report.md` 里 3 处 `82` 分别是`116.82`（Tanaka 算式）、`82 → 66.0`（综合分口算）、`app 82 个 .py`（扫描面），都与 2xx 无关。故**没有可改的地方**。本波做的是：把 **83/91** 用运行时口径重新量了一遍（`openapi()["paths"]`，见第 ⑧ 节）并写进本报告，同时确认那 8 个不带 schema 的 2xx **正是 8 个 `204 DELETE`**。⚠️ 刻意**没有**去编辑 `progress.md`：它是 193 479 B / 929 个裸 LF / 无 BOM 的文件，而派单第 1 节逐字禁止用编辑器工具反复改 `.superpowers/` 下的文件（Plan 02 曾因此永久丢掉约 107 KB）—— 为一句已经自我更正的话去动它，风险收益不成比例。
3. **I4 的「若你认为去掉字段会破坏什么，顶回来」那一支没有触发** —— 实测确认`demo_data` 走的是 `repo.upsert`（不经 schema）、`open_rpe` 是正主、`ClassSessionRead` 仍含那一列，故去掉字段**不破坏任何东西**，于是按派单的首选做了（去掉字段），没有退到 `field_validator` 那一支。唯一红掉的既有断言是 `test_every_read_schema_covers_exactly_the_model_columns`，已按硬规矩 #88 收进来（新增 `_SERVER_FILLED_COLUMNS` 字面清单 + 反向断言）。

### 7.3 关切（新登记的，按严重度排）

1. **【移交 Plan 04，中】`class_session.rpe_token` 对匿名调用方可读。**I4 把那一列从**写**侧摘掉了，但 `ClassSessionRead` 仍然含它，而本波（照裁定）让 `GET` **一律匿名** —— 于是 `GET /api/class-sessions/{id}`不带头就能读到课堂口令，学生因此可以绕过「教师投屏」直接拿到口令交快评。⚠️ `app/api/schemas/dashboard.py` 那一侧是**刻意不含**它的（那里逐字写着「口令是给学生端**提交时**用的」），故这是一个不对称。**不在本波修**的理由：修法要么给 `class-sessions` 一个窄化的读模型、要么把 `rpe_token` 放进 `list_exclude`，两者都会改掉`test_every_read_schema_covers_exactly_the_model_columns` 第一拍「`*Read` 与 DB 列逐字对齐」的口径 —— 那是一次**有意的口径变更**，该由控制者裁定，不该在一个 fix 波里顺手做。已逐字写进 `_SERVER_FILLED_COLUMNS` 的注释。
2. **【移交 Plan 04，中】「两条不同规则 + 真并发」这一格没有裁判。**第四道闸门是 SELECT-then-INSERT，两个进程同时 SELECT 都看不见对方时仍会各写一行；而第三道（四列唯一约束）的键里含 `reason`，挡不住「两条不同规则」。真正的修法是 `(prescription_id, week, source)` 的**部分唯一索引**（`WHERE source='auto'`），那是一次 DDL 变更（本仓不做迁移）。⚠️ 单进程内不可达（管道逐学生串行、教师端一次一个请求），故本波只如实记录。已写进 `_auto_adjustment_exists` 的 docstring。
3. **【移交 Plan 04，低】`POST /api/pipeline/run-daily` 不注入 `now`。**生产口径下 `as_of == 今天`，故等价；但演示库的 `as_of` 是历史日，手工点那一条会让 `alert.triggered_at` 落到真实时钟上、`weekly_class_report.alert_summary` **变回 9 个 0**。已在 `demo.ps1` 的提示块里逐字警告（并给出「要重灌请重跑 demo.ps1」）。⚠️ 没有去改那个端点：把它的 `now` 也改成 `business_now(business_date)` 会让生产路径上的 `alert.triggered_at` 从「真实时刻」变成「当天 00:00」，那是一次口径变更，该由控制者裁定。
4. **【移交 Plan 04，低】`weekly_adjustment.source='teacher'` 仍无生产写入方。**见顶回 1。C1 选 A 之后，`weekly_training_sheet` 的「相乘」在生产路径上退化成一个恒等式（至多一条 `auto`），故「多条相乘」这件事今天**只有测试覆盖**。Plan 04 若给教师端加「手工调整本周量」的入口，那一格才会活过来 —— 而届时文案已经是从库里实读的，不会再出现「文案说 20%、学生看到 36%」。
5. **【本波顺手清掉的】`app/api/routers/alerts.py` 的 `AUTO_REDUCTION_FACTOR` 导入已去掉**（文案改成实读之后它在本模块不再被用到，留着就是一个假的所有者）。`app.pipeline.alert_stage.AUTO_REDUCTION_FACTOR` 本身**没动**（`tests/domain/test_report.py` 与 `tests/pipeline/test_alert_stage.py` 各有一份字面钉）。

### 7.4 待清扫（**4 条**）

1. **M1 的窄化读模型**（`*ListRead`）归 Plan 04 —— 本波只把 **83/91** 这个数用运行时口径复核了一遍（并确认那 8 个不带 schema 的 2xx 正是 8 个 `204 DELETE`），**没有**动 `crud.py:544-555` 那个取舍（终审认可它）。
2. **M3（`AlertReport.errors` 在库里没有痕迹）** 按派单**不在本波修**，归 Plan 04 的 backlog（处置是 `errors > 0` 时把 `run.status` 降成 `"partial"`，一行改动）。
3. **`YELLOW_CLASS_RPE_HIGH` 在演示库上仍不触发**（班级均值 6.93 < 7.0）—— 要让 5 条规则在演示库里全出现，得动 `demo_data` 的 RPE 分布，而那会动它的幂等口径（`16/480/1680/480`）。留给需要它的人。
4. **`prescription.status='needs_review'` 与那批 addon warning 的差别**（`demo_bootstrap` 里逐字印着的那一段）此前就登记为待清扫，本波**原样保留**、没有动。

### 7.5 一次工具事故（已修，如实记录）

编辑工具在给 `backend/scripts/demo.ps1` 打补丁时**吃掉了它的 UTF-8 BOM**（`bytes 9750 / bom=True` → `bytes 11044 / bom=False`）。⚠️ 后果是真的：PowerShell 5.1 对**无 BOM** 的 `.ps1` 按系统 ANSI 代码页解码，而本文件满是中文，于是 `Write-Host` 会打出乱码、极端情况下连解析都会错。**发现方式**是本波自己立的那道纪律（改文件前后都用 `read_bytes()` 量行尾与 BOM），**修法**是用 python 把 BOM 加回去（先证明内容确实还是合法 UTF-8、且没有混进裸 LF），并**真跑了一次** `demo.ps1 -DryRun` 验证：退出码 0、中文正常、`禁区复核：backend\pe.db 不存在、backend\data\seed\ 仍为 0 文件 ✓`。最终字节：`11047 B / crlf 184 / lf_only 0 / bom True`，`git diff --numstat` = `15 insertions / 2 deletions`（**没有**整文件重写）。

⚠️ 记一笔教训：`.ps1` 与 `.py` 在这一格上不一样 —— `.py` 有没有 BOM 无所谓，`.ps1` 有中文就**必须**有 BOM。本仓的 `.gitattributes` 把 `.superpowers/**` 钉成 `-text`、把 `backend/data/**` 钉成 `eol=lf`，但**没有**给 `*.ps1` 钉 `working-tree-encoding`，故 BOM 完全靠人守。

---

## ⑧ 最终验收

### 8.1 测试与覆盖率

| 格 | 基线（`20797e7`） | 本波（`fix/plan-03-review-findings`） |
|---|---|---|
| `python -m pytest -q` | 1244 passed | **1251 passed**（166.47 s） |
| 带 `--cov=app.domain --cov-branch` | 1243 passed, 1 skipped | **1250 passed, 1 skipped**（336.25 s） |
| `app/domain/` Stmts | 1268 | **1268** |
| `app/domain/` **Miss** | 0 | **0** ✅ |
| `app/domain/` Branch | 376 | **376** |
| `app/domain/` **BrPart** | 0 | **0** ✅ |
| `app/domain/` Cover | 100% | **100%** |

`TOTAL 1268 0 376 0 100%` —— 四格逐字不变（本波对 `app/domain/` 只改了一处 docstring：`prescription/weekly.py` 里 `weekly_training_sheet` 那段散文，故 stmts / branch 都没动）。**既有 1244 条测试一条都没退步**，+7 条新守卫：

1. `tests/pipeline/test_alert_stage.py::test_two_different_red_rules_in_the_same_week_reduce_once_not_twice`
2. `tests/api/test_crud.py::test_every_writable_resource_declares_require_teacher_explicitly`
3. `tests/api/test_crud.py::test_every_writable_resource_rejects_an_anonymous_mutation`
4. `tests/api/test_feedback.py::test_every_literal_tailed_special_route_beats_the_generic_placeholder_route`
5. `tests/pipeline/test_daily.py::test_replaying_a_historical_day_lands_the_alerts_inside_the_report_window`
6. `tests/pipeline/test_daily.py::test_business_now_accepts_both_a_string_and_a_date`
7. `tests/pipeline/test_backfill.py::test_run_backfill_injects_each_business_day_as_now`

（另有 3 条既有测试被**改造**而不是新增：`test_a_duplicate_auto_adjustment_…（加 monkeypatch 模拟并发）、`test_the_identity_headers_…security_schemes`（第 ③ 拍口径）、`test_the_factory_rejects_a_bad_configuration`（六道 → 七道）。）

### 8.2 计数面

| 格 | 基线 | 本波 | 备注 |
|---|---|---|---|
| 表 | 25 | **25** | 一张没加没减（本波零 DDL） |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33** | `app/db/models/` 一个字没动 |
| 扫描面 | 60 | **60** | pipeline 10 + db 11 + domain 18 + api 21；本波没在 `app/` 下新增文件 |
| `/api/` 路径模板 | 63 | **63** | 没加没减端点 |
| 操作 | 91 | **91** | 同上 |
| 挂 `security` 的操作 | 18 | **44** | 18 特例 + 26 CRUD 写入（9 POST + 9 PATCH + 8 DELETE） |
| mutating 操作 | 35（9 带 / 26 不带） | **35（35 带 / 0 不带）** | 终审那条 Important 归零 |
| 2xx 带 schema | 83/91 | **83/91** | M1 那个数复核；8 个不带的正是 8 个 `204 DELETE` |
| `securitySchemes` | 2 | **2** | 没新增第三个 scheme |
| spec 顶层 `security` | `None` | **`None`** | 仍按端点声明 |
| 黄金用例 | 14 | **14** | `test_golden_cases.py` 收 19 条，参数化的是 `GC01`…`GC14` |
| `len(app.routes)` | 6 | **6** | 假绿口径，仅记录 |

### 8.3 五个指纹（`sha256[:16].upper()`，CRLF 归一化为 LF，逐个从磁盘现算）

| 指纹 | 文件 | 字节 | 逐字不变 |
|---|---|---|---|
| `D2C8E539E2FA0029` | `backend/data/national_standard_2014.csv` | 21412 | ✅ |
| `5394B37F01DAC9AC` | `backend/data/exercises.yaml` | 23247 | ✅ |
| `822CB86A5E998301` | `backend/data/exercise_equivalence.yaml` | 8245 | ✅ |
| `E48E3AC82BB45BB7` | `backend/data/alert_rules.yaml` | 6037 | ✅ |
| 18 套处方模板 | `backend/data/prescription/*.yaml` | 5710–7930 | ✅ **18 个** |

（另两份不在那五个里、也一并量了、同样没动：`data/indicator_ranges.yaml` = `1962FEC6FB2CA852`、`data/README_national_standard.md` = `5CCE72B74D1EB711`。）

### 8.4 禁区

```
git diff 20797e7 HEAD -- backend/data          → 空   ✅
git diff 20797e7 HEAD --stat -- backend/data   → ''   ✅
git diff HEAD -- backend/data                  → 空   ✅（工作树也没动）
backend/pe.db exists                           → False ✅
backend/data/seed/ 的文件数（含子目录，rglob）  → 0    ✅
```

⚠️ 全程**没有**跑 `python -m app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`（三个 CLI 的 `main()` 把缺省值写死在两个禁区上）。要数据集就在 python 里 `build_dataset(cfg)`；要演示库就走 `demo_bootstrap`（它自带两道禁区守卫，本波还把那两道**加宽**了，见 8.6）。所有探针脚本都放在 `$env:TEMP/pe_probe/` 下、**一个都没进 `backend/`**（硬规矩 #108：架构守卫会 AST 解析工作树里全部 `.py`，含未入库的）。

### 8.5 真机跑通

`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\demo.ps1 -DryRun` → **退出码 0**，中文正常（BOM 已还原），六步全过、`offenders` 六格全过、`禁区复核：backend\pe.db 不存在、backend\data\seed\ 仍为 0 文件 ✓`、`-DryRun 收尾：<TEMP>\pe_demo_dryrun_<PID> 已删掉`。

### 8.6 M2（顺手修了）

`scripts/demo_bootstrap.py` 那两道禁区守卫的窄口径按终审建议加宽，并**实测五个输入全部被拒**（探针 `$env:TEMP/pe_probe/p6_guards.py`）：

| 输入 | 修前 | 修后 |
|---|---|---|
| `--db-url sqlite:///<backend>/pe.db` | 拒 | **拒** |
| `--db-url sqlite:///<backend>/PE.DB`（大小写不同） | **放行** ❌ | **拒** ✅（`make_url(...).database` + `Path.resolve()` + `os.path.normcase`） |
| `--db-url sqlite:///<TEMP>/pe.db`（basename 恰好 pe.db、在禁区外） | 拒 | **拒**（保留这一支） |
| `--csv-dir <backend>/data/seed` | 拒 | **拒** |
| `--csv-dir <backend>/data/seed/2025`（子目录） | **放行** ❌ | **拒** ✅（`is_relative_to`） |

`scripts/demo.ps1:133` 的 `Get-ChildItem $ForbiddenCsv -File` 加了 **`-Recurse`**（不带它看不见 `data/seed/2025/` 下的文件，于是那一档会静默通过复核）。

⚠️ 如实记录：终审说这一条「今天结构上碰不到」（`demo.ps1` 是唯一调用方、`$DbUrl` 从 `app.main.DEMO_DB_URL` 单点读出、`$CsvDir` 恒在 `$env:TEMP`），故本波这三处是**纯加固**、不修任何现存失效。

### 8.7 commit

| sha | 一句话 |
|---|---|
| `273290f` | **C1（选 A）**：一处方一周至多减一次 + 文案改成从库里实读 + 「三道闸门」改四道 + 3 处守卫 + 变异取证 |
| `d75564a` | **写入侧加强制**：`build_crud_router(require_teacher=)` + 9 个可写资源逐个置位 + 2 条遍历型守卫 + 那条全仓级断言的口径改写（18 → 44） |
| `182be18` | **I4 + I3**：`rpe_token` 从泛型写侧摘掉（含 `_SERVER_FILLED_COLUMNS` 那份清单）+ 路由顺序警告搬进 `app/api/routers/__init__.py` + 清单式守卫 |
| `2cc6222` | **I1 + I2 + M2**：`run_daily` 的 `now` 可注入（`business_now`）+ 演示库跑两次管道 + `offenders` 3 → 6 格 + 两道禁区守卫加宽 |
| `<本报告>` | 收尾：本报告 + C1 docstring 里一处悬空测试名的更正 |

⚠️ 派单建议 4–5 个 commit，本波是 **5** 个（第 5 个是报告本身 + 一处 docstring 更正：我在 `_write_auto_adjustment` 的 docstring 里先写了一个并不存在的测试名`…_and_the_pre_insert_select_is_what_stops_the_second_one`，变异取证按硬规矩 #83 做在源码上、不是一条常驻测试，故把那一句改成指向本报告 —— 一个悬空的测试名就是一句谎，按本仓的规矩必须当场清掉）。

---

## 附：本波用过的探针（全在 `$env:TEMP/pe_probe/`，跑完删掉，仓库里零残留）

| 探针 | 用途 |
|---|---|
| `p1_baseline.py` | 在 TEMP 下跑一遍 `demo_bootstrap`，量演示库的三层完成率 / `notification` / `alert_summary` / 处方训练日模式 / 逐日打卡 |
| `p2_openapi.py` | 用 `openapi()` 量 63/91/18/35、83/91、25 表、扫描面 60、`len(app.routes)` |
| `p3_eol.py` | `read_bytes()` 量每个待改文件的 CRLF / 裸 LF / BOM（改前改后各跑一次） |
| `p4_factor.py` | 复用 `test_alert_stage` 的夹具，直接量「两条红色同周」那一周的 `sheet.factor` |
| `p5_sec.py` | 写入侧加强制之后的 OpenAPI 面 + 「空 body 的 POST 是 401 还是 422」 |
| `p6_guards.py` | `demo_bootstrap` 两道禁区守卫的 5 个输入 + 一次完整跑 + 禁区复核 |
| `p7_ledger.py` / `p8_ledger2.py` / `p9_find82.py` | 用 `Grep` + 定点窗口从 193 KB 的账本里只取出「82/90」那几段上下文（不整文件读进上下文） |
| `p10_accept.py` | 最终验收面：全部指纹 / 禁区 / git / OpenAPI / 表 / 扫描面 |
| `mutate.py` / `mutate_gen.py` | 变异器（按字节替换 + 备份 + sha256 + 清 `__pycache__` + 还原） |
| `fix_bom.py` | 把 `demo.ps1` 被编辑工具吃掉的 UTF-8 BOM 加回去 |

5 次变异、5/5 killed，每次还原都做了三重取证（sha256 复原 + `git diff` 复原 + 复跑全绿）：

| # | 变异 | 红在哪 |
|---|---|---|
| 1 | 删掉 `_write_auto_adjustment` 里那道 SELECT（734 B） | 新单元测试红在 `adjustments_written == 2`；端到端红在推送文案报出 `0.64` / `36%` |
| 2 | `if require_teacher:` → `if False:` | 遍历型守卫红（POST 变 422）+ 全仓级断言红（少 26 项） |
| 3 | 只留 `Security(...)`、删掉 `Depends(_require_teacher_identity)` | **只有**遍历型守卫红 —— 声明面那条绿，正是「spec 上写了、实际谁都放行」 |
| 4 | `include_router` 顺序排反（`feedback` 挪到 `catalog` 之后） | 清单式守卫 + 既有点状守卫一起红，报错逐字是 `loc ["path","mini_test_id"]` / `input "normalized"` |
| 5 | `run_daily` 忽略注入的 `now`；`run_backfill` 不传 `now` | I1 的两条守卫分别红（`generated_at` 是真实时钟 / `seen` 里全是 `None`） |

