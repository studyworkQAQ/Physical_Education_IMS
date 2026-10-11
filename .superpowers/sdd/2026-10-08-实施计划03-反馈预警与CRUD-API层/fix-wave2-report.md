# Plan 03 收尾小修波（fix wave 2）实现者报告

**分支** `fix/rpe-token-and-spec13`（从 `main` 的 `9c540d5` 起）
**范围** 两件事：① `class_session.rpe_token` 对匿名调用方可读；② spec §13「运行方式」照它跑会破两个禁区。
**结论** 两件都落地。**1255 passed**（1251 + 4 条新守卫），`app.domain` 覆盖率四格**逐字不变**
（1268 / 0 / 376 / 0 / 100%），禁区五指纹逐字不变，`backend/data/**` 一个字节没动。
**顶回 / 更正控制者 5 处**（其中 1 处是 Critical：派单给的落地步骤只堵住了洞的一半）。

---

## ① 环境与基线复现

硬规矩 #73 那一行先跑：

```
python -c "import sqlalchemy, fastapi, pydantic, yaml; print(sqlalchemy.__version__, fastapi.__version__)"
→ 3.11.1 (tags/v3.11.1:a7a450f, Dec  6 2022, 19:58:39) [MSC v.1934 64 bit (AMD64)]
→ sqlalchemy 2.1.3   fastapi 0.141.1   pydantic 2.13.5   PyYAML 6.0.3
```

**没有撞上 `ImportError: DLL load failed`**，故没有停手报回。无 venv，系统 Python。

开工时的仓库状态：`git status` 干净、`HEAD = 9c540d5`、`git branch --show-current = main`。
建分支后 `git branch --show-current = fix/rpe-token-and-spec13`。**全程没有 push、没有碰 main。**

基线复现（全部亲跑）：

| 项 | 派单给的基线 | 实测（开工时） |
| --- | --- | --- |
| `python -m pytest -q` | 1251 passed | **1251 passed**（145.66 s） |
| `--cov=app.domain --cov-branch` | 1268 / Miss 0 / 376 / BrPart 0 / 100% | **1268 / 0 / 376 / 0 / 100%**（1250 passed, 1 skipped，247.26 s） |
| 表数 | 25 | **25** |
| 扫描面 | 60 | **60**（`SCANNED_DIRS = ('pipeline', 'db', 'domain', 'api')`） |
| `/api/` 路径模板 / 操作 | 63 / 91 | **63 / 91** |
| 挂 `security` 的操作 | 44 | **44** |
| `len(app.routes)`（假绿参考） | —— | **6**（⚠️ 与派单的警告逐字吻合：FastAPI 0.141.1 的 `include_router` 折叠成一个 `_IncludedRouter`，故本波所有端点计数一律走 `app.openapi()["paths"]`） |
| 四个 refdata 指纹 | `D2C8E539E2FA0029` / `5394B37F01DAC9AC` / `822CB86A5E998301` / `E48E3AC82BB45BB7` | 四个**逐字相同** |
| 18 套处方模板 | 18 | **18 个 `.yaml` / 合计 123 848 B**；按 stem 排序拼接的合计指纹 `83DA02814A29679C` |
| `backend/data/**` 全量 | —— | **24 个文件**，全量指纹 `DD64C37D7D48057B`（改前改后各量一次，逐字相同） |
| 禁区 | `pe.db` 不得存在、`data/seed/` 0 文件 | `pe.db exists: False`、`data/seed` 存在且 **0 文件** |

指纹口径（与 `tests/test_refdata.py` / `test_refdata_prescription.py` / `test_refdata_alerts.py` /
`tests/domain/test_prescription_templates.py` 四处逐字相同）：
`sha256(read_bytes().replace(b"\r\n", b"\n"))[:16].upper()`。

---

## ② 第一件的落地：`rpe_token` 不再匿名可读

### ②.1 ⚠️⚠️ 顶回 1（Critical）：派单的落地步骤只堵住了洞的**一半**

派单第 1 条第 1 步是「把 `rpe_token` 从 `ClassSessionRead` 去掉」，而它对洞的描述是
「任何人 `GET /api/class-sessions` 就能读到全部口令」。

**实测：泛型 list 端点根本不走 `response_model`。** `app/api/crud.py` 的 `_list` 逐字是：

```python
rows = session.execute(
    select(*[getattr(model, name) for name in kept]) ...
).all()
return {"items": jsonable_encoder([dict(zip(kept, row)) for row in rows]), ...}
```

那个端点的 docstring 自己解释了为什么：「含全部列的 `response_model` 会让 FastAPI 在序列化
阶段 `getattr` 每一个字段，被 `defer` 掉的列于是触发 N+1 的延迟加载，『排除大 JSON 列』的
性能收益当场归零」。

于是**只摘读模型堵住的是 read-one / POST / PATCH 三个端点**，而
`GET /api/class-sessions`——**正是派单自己点名的那个 URL**——照旧原样返回全部口令。

**我是怎么发现的**：守卫 ① 里写了「list 的响应体里不许出现那串口令」，它当场红：

```
>       assert "rpe_token" not in listing.json()["items"][0]
E       AssertionError: assert 'rpe_token' not in {'id': 1, 'course_section_id': 1,
                        'session_date': '2025-09-01', 'period': 3, ...}
```

**⚠️ 若照派单字面做完，全量测试会 1251 全绿**（派单没要求断 list，而既有守卫里没有一条
量「list 的键集合 ⊆ 读模型的字段集」——恰恰相反，
`test_every_resource_list_omits_json_text_columns_and_read_one_includes_them`
的第一拍把 list 的键集合钉成「全部列 − JsonText 列」，即**期望 list 比 read-one 多**）。
**洞会原样留着，而报告上会写「已修」。**

**修法**：给 `catalog.py` 的 `/api/class-sessions` 那一行显式传
`"list_exclude": ("rpe_token",)`——23 行里**唯一**一行显式传这个参数
（它此前是「有能力、无生产调用方」的一档，由一条合成资源的测试跑通）。

于是「一个秘密列不再匿名可读」在本仓有**三处**住址，缺一处洞就还在：

| 住址 | 挡的是 | 守卫 |
| --- | --- | --- |
| `ClassSessionRead` 去掉那一格 | read-one / POST / PATCH 的响应体 | `_SERVER_GENERATED_HIDDEN_COLUMNS` + 对齐断言 |
| `RESOURCES` 那行的 `list_exclude` | **list 的响应体** | 遍历守卫新加的两拍 + 守卫 ① |
| 新的教师端窄门 | 教师仍然读得到 | 守卫 ②③④ |

### ②.2 `ClassSessionRead` 的新列数与两个清单常量

**`ClassSessionRead`：7 列 → 6 列**
（`id` / `course_section_id` / `session_date` / `period` / `rpe_opened` / `batch_id`，
声明顺序与 DB 列序一致、只少 `rpe_token` 那一格）。
⚠️ 它是**本仓第一个「与 DB 列不逐字对齐」的 `*Read`**。

`tests/api/test_crud.py` 现在有**两份**清单，语义不同、刻意不合并：

| 常量 | 哪一档 | 影响哪些模型 | 今天的内容 |
| --- | --- | --- | --- |
| `_SERVER_FILLED_COLUMNS` | **档 1：服务端填、但要暴露**（客户端传了会被 Pydantic 静默丢掉，读侧仍然看得见） | `*Create` / `*Update` | `{"/api/class-sessions": ("rpe_token",)}` |
| `_SERVER_GENERATED_HIDDEN_COLUMNS` | **档 2：服务端生成、且是秘密**（读侧也不许出现） | `*Read` | `{"/api/class-sessions": ("rpe_token",)}` |

⚠️ 两个常量的 `#:` 注释块各自**逐字写明自己是哪一档**、以及为什么不合并
（「一份合并的清单会说不清『哪一半被摘掉了』」）。`rpe_token` **同时**在两个清单里
（它既写不进去、也读不出来），这是有意的：档 1 的那一半是终审 I4 的成果，本波没动它。

**对齐断言的改法（派单第 1 条第 1 步要求「不削弱它原本挡的东西」）**：

```python
hidden = _SERVER_GENERATED_HIDDEN_COLUMNS.get(spec["path"], ())
assert list(spec["schemas"].read.model_fields) == [
    c for c in columns if c not in hidden
], spec["path"]
for name in hidden:
    assert name in columns, (spec["path"], name, "清单里点名的不是该表的列")
    assert name not in spec["schemas"].read.model_fields, (spec["path"], name)
...
assert counted == 41                                    # 不变
assert len(_SERVER_GENERATED_HIDDEN_COLUMNS) == 1       # 新增
assert sum(len(v) for v in _SERVER_GENERATED_HIDDEN_COLUMNS.values()) == 1   # 新增
```

它**没有**被削弱，三理由：

1. 期望侧仍然是 `model.__table__.columns`（SQLAlchemy 元数据）、被测侧仍然是
   `BaseModel.model_fields`（Pydantic 元数据），**两侧不同源**没变；
2. 例外是**按 `path` 精确点名到列**的，且**反向也钉**（点名的列必须①真是该表的列、
   ②真不在读模型上）。于是「往清单里塞一个列名来绕过对齐断言」会让②红——
   除非它真的从 `*Read` 上摘掉了，而那正是本条要它做的事；
3. **例外清单的大小也被钉住**（恰好 1 格 / 1 列）。少了这两行，「嫌对齐断言碍事、
   往里加第二行」是一次**静默**的改动——原有的①②两拍对它完全无感
   （加进去的列只要真的不在读模型上，①②都绿）。

⚠️ 遍历守卫 `test_every_resource_list_omits_json_text_columns_and_read_one_includes_them`
也改了：它的期望侧原本是「全部列 − JsonText 列」，现在是「全部列 − JsonText 列 − 秘密列」，
另加两拍（秘密列在 **list 与 read-one 里都不许出现**）与一拍
（**恰好 1 行**显式声明 `list_exclude`）。⚠️ 期望侧**不读** `spec["list_exclude"]`
——两侧同源的话，「忘了写那一行」会同时改掉两边、断言恒成立。
⚠️ 这三拍都**不空转**：`seeded` 夹具给 `class_session` 那一行填的是非空的 `"ABC12345"`。

### ②.3 新端点

```
GET /api/class-sessions/{class_session_id}/rpe-token
```

| 项 | 值 |
| --- | --- |
| 身份 | `Depends(current_teacher)` + `require_teacher(session, staff_no)` + `dependencies=[Security(TEACHER_STAFF_NO_SCHEME)]`（与 `open-rpe` **同档**） |
| 码 | 200（有口令）/ **401**（缺头或空白）/ **403**（工号不在册）/ **404**（课次不存在）/ **409**（没有口令可读） |
| 响应模型 | 新增 `RpeTokenRead`，**两格**：`class_session_id: int` / `rpe_token: str` |
| tags | `["class-sessions"]` |
| 住址 | `app/api/routers/feedback.py::read_rpe_token` |

**它不重新生成口令**：只 `_get_or_404` 之后把库里那一串原样回出去。
⚠️ `rpe_opened` **刻意不在**响应模型里——本端点在「没发起」时回 409，故一个 200
**必然**意味着已发起；再带一格恒为 `True` 的布尔，是给前端一个可以自相矛盾的地方
（`{"rpe_opened": false, "rpe_token": "…"}` 这个组合在结构上就写不出来）。

### ②.4 `rpe_opened` 为假时返回什么：**409 + `code = "rpe_not_opened"`**（我的裁定与理由）

派单把这一档留给我定（409 或 404 + 一个明确的 `code`）。我选 **409**，
并**复用**既有的 `CODE_RPE_NOT_OPENED`（`submit_rpe` 第三道闸门用的就是它）。三条理由：

1. **不是 404**：课次**存在**（不存在那一档已经由 `_get_or_404` 回 404 了），
   缺的是它的**状态**。而 404 的 `code` 是 `not_found`，与「资源不在」**同形**，
   前端就分不清「课次 id 传错了」与「老师还没点发起」——这两种提示教师要做的事完全不同。
   这也与本模块既有口径逐字一致：`CODE_RPE_NOT_OPENED` 的注释写着
   「用 **409** 不用 422：请求体本身没有错，错的是**资源的状态**」。
2. **与 `submit_rpe` 逐字同码**：同一件事（「这节课还没发起快评」）在学生侧就是
   409 `rpe_not_opened`。给两个码，前端就要维护两张对照表；而「一件事只该有一种说法」
   是本仓既有的纪律（`submit_rpe` 的 docstring 里那句「『撞自然键』这件事全仓只该有一种说法」）。
3. **不是 `null`**：`{"rpe_token": null}` 把「不知道」讲成「口令是空的」——本项目最响的
   那条纪律。于是 `RpeTokenRead.rpe_token` 是 `str` 而不是 `str | None`，
   **结构上**写不出一个带 `null` 口令的 200（守卫 ④ 的最后一拍钉它：
   `RpeTokenRead.model_fields["rpe_token"].annotation is str`）。

⚠️ **判据抽成了一个共用的谓词** `_rpe_is_open(row) -> bool`
（`row.rpe_opened and row.rpe_token is not None`），**三个**消费者共用一个所有者：
`open_rpe` 的 `already_open`、`submit_rpe` 的第三道闸门、`read_rpe_token` 的准入判定。

**为什么这一格不能各写一遍**（失效形态是具体的、而且它看起来像别人的错）：
`rpe_opened` 在 `ClassSessionUpdate` 上而 `rpe_token` 不在（终审 I4），
故一发泛型 `PATCH {"rpe_opened": false}` 就能造出「开关是 `False` 而口令**留在库里**」。
那一刻「库里有一串口令」与「学生交得上来」**不是一回事**：
若 `read_rpe_token` 只判 `row.rpe_token is not None`，教师端就会读到一串口令、投屏、
学生交上来 **409**——而那看起来像学生抄错了。守卫 ④ 的第 ③ 拍**真的造出这一档**
（一发 PATCH），并断言**两个端点给同一个 409、同一个 `code`**。

### ②.5 路由顺序：**实测不承重**（派单第 3 条）

新端点是**四段**（`/api` `class-sessions` `{class_session_id}` `rpe-token`），
泛型工厂给 `class-sessions` 注册的读端点是**三段**
（`GET /api/class-sessions/{class_session_id}`），两者**不同形**，
故「特例必须在 `catalog` 之前」那条纪律对它不构成约束。

**实测证据两个口径**（**都不用 `app.routes`**）：

① `app.openapi()["paths"]` 的**插入序**（`feedback` 先 include，故它的三个路径排在
`catalog` 那两个之前）：

```
/api/class-sessions/{class_session_id}/open-rpe   ['post']
/api/class-sessions/{class_session_id}/rpe-token  ['get']     ← 本波新增
/api/class-sessions/{class_session_id}/rpe-status ['get']
/api/class-sessions                               ['get', 'post']
/api/class-sessions/{class_session_id}            ['delete', 'get', 'patch']
```

② **实发请求**（守卫 ③）：那一发 200 就是证据——被三段那条吃掉的话路径根本匹配不上
（**404**）。守卫 ③ 另附注册面一拍（它是 `paths` 里**自己的一个键**、
`sorted(paths[key]) == ["get"]`、`security == [{"X-Teacher-Staff-No": []}]`），
以及「泛型的三段读端点照常 200」（两条路由共存，不是「特例抢走了整个前缀」）。

⚠️ **`include` 顺序核实过**：`app/api/routers/__init__.py` 的 `api_router` 依次 include
`feedback` → `prescription` → `alerts` → `dashboard` → `pipeline` → `catalog`，
`feedback` **仍然排在 `catalog` 之前**，故即便将来有人给 `class-sessions` 加一个四段的
泛型路径也不会撞车。**没有发现遮蔽。**

⚠️ **我没有把新路径加进 `_LITERAL_TAILED_SPECIAL_ROUTES`**（那份清单式遮蔽守卫）。
理由：那份清单的**实际**判据不是它 docstring 写的「末段为字面量」，而是
「**与泛型 `{path}/{pk}` 同形（三段）**」——今天 3 项全是三段，而
`open-rpe` / `rpe-status` / `alerts/{id}/handle` / `notifications/{id}/read` /
`students/{id}/home` 这些**四段**的字面末段特例路径**一个都不在列**。
新端点是四段，加进去会与该清单的既有形状不一致；它的遮蔽由守卫 ③ 的实发请求钉。
⚠️ 那份清单的 docstring 措辞与它自己的内容有出入，已登记为待清扫（§④.1）。

### ②.6 四条守卫的名字

全部住在 `backend/tests/api/test_feedback.py` 的批次 B（课堂快评）里：

| # | 名字 | 钉什么 |
| --- | --- | --- |
| ① | `test_the_rpe_token_is_absent_from_the_anonymous_class_session_read_response` | 匿名 `GET /api/class-sessions`（list）与 `GET …/{id}`（read-one）里**没有** `rpe_token` 这个键、且**那串口令的子串不出现**在响应体里；+ 结构面（`model_fields` 与 OpenAPI component schema）；+ **反证**（库里确实有口令、教师那扇窄门确实读得到 → 守卫不空转） |
| ② | `test_the_rpe_token_route_rejects_an_anonymous_caller_with_401` | 匿名 → **401**；工号不在册 → **403** `forbidden`；课次不存在 → **404** `not_found`；且三档的响应体里都不含口令 |
| ③ | `test_the_rpe_token_route_returns_the_token_that_open_rpe_made_verbatim` | **两侧不同源**（一侧来自 `open-rpe` 的响应、一侧来自新端点的响应）逐字相同；连读两次同一个串（现生成的话第二次必然不同）；库里那一行没被改过；再点一次 `open-rpe` 仍 `already_open=True` 且口令不变（窄门无副作用）；+ 注册面与「泛型三段读端点照常 200」 |
| ④ | `test_the_rpe_token_route_is_409_when_there_is_no_token_to_read` | 三档逐个实发：没发起 → 409 `rpe_not_opened`；发起了 → **200**（对照，防「恒 409」）；**PATCH 把开关单独翻下去而口令留在库里** → 教师侧与学生侧给**同一个** 409 同一个 `code`；+ `RpeTokenRead.rpe_token` 的标注是 `str`（结构上写不出 `null` 口令的 200） |

⚠️ 派单要求的第 ④ 条守卫（「挂 `security` 的操作数从 44 变成 45，并把钉住这个数的断言改掉」）
**不是新测试**，而是既有守卫 `test_the_identity_headers_are_registered_as_openapi_security_schemes`
（`tests/api/test_prescription_api.py`）的**三处**改动：`expected` 清单 18 → **19** 项、
末尾 `len(all_security) == 44` → **45**、`len(expected) == 18` → **19**。

**按硬规矩 #88 先跑全量找出所有钉它的地方**：改完读模型 + 加完端点之后跑一次全量，
**红了恰好 2 条**，两条都是预期的：

```
FAILED tests/api/test_crud.py::test_every_read_schema_covers_exactly_the_model_columns
       - AssertionError: /api/class-sessions
FAILED tests/api/test_prescription_api.py::test_the_identity_headers_are_registered_as_openapi_security_schemes
       - AssertionError: 只读的 GET 端点不该带 security：大屏与列表要能不登录就读
2 failed, 1249 passed
```

第二条红的方式很有信息量：新端点是一个**带 `security` 的 GET**，而它不在 `expected` 里，
于是落进 `crud` 那一圈、撞上「只读的 GET 端点不该带 `security`」那一拍。
**这正是那条守卫设计出来的行为**（它的 docstring 逐字写了「Task 8/9 每加一个带身份的
特例端点都要回来往这份清单里加一行——这是有意的」）。

### ②.7 挂 `security` 的操作数：44 → **45**

`19 个特例 + 26 个 CRUD 写入 = 45`（26 = 9 POST + 9 PATCH + 8 DELETE，
`semesters` 是 `on_delete="forbid"`、不注册 DELETE，故不是 27）。运行时口径实测：
`operations with security: 45`。

### ②.8 连带更正的三处「指向错误门」的文档

派单没要求，但**不改就是把 Plan 04 指向一扇已经关掉的门**（终审 I4 批评的正是这个失效形态）：

| 住址 | 改前 | 改后 |
| --- | --- | --- |
| `app/api/schemas/dashboard.py::PendingRpeRead` | 「学生从卡片点进去时再调 `GET /api/class-sessions/{id}` 取」 | 明写那句**已不成立**：那一格已从读模型摘掉、替代它的窄门要**教师头**，故**学生端的口令只能来自教师课堂投屏**（spec §8.1 的原意），前端不要指望从任何 API 读到它 |
| `app/api/schemas/feedback.py::ClassSessionCreate` | 引旧谓词字面量 `not row.rpe_opened or row.rpe_token is None` | 改引 `_rpe_is_open`（谓词有了唯一所有者，字面量抄两处会漂） |
| `app/api/routers/feedback.py::open_rpe` | 同上 | 同上 |

另按实际改写了 `routers/feedback.py` 模块 docstring 的四处计数
（「七个特例端点」→ 七个 + 一个；端点表加一行；「教师侧四个」→ **五个**；
「四个端点都挂 `Security`」→ **八个**）与一句过期判断
（「任何在册教师可以跨班这句话今天只对**写入端点**成立」→ 只对
「**没挂任教关系闸门的那些端点**」成立；⚠️ 改前那句就已经不准确了：
`rpe-status` 与 `mini-tests/normalized` 两个也是 `GET`），
以及 `schemas/feedback.py` 的「本段这 13 个是七个特例端点用的」→ **14 个 / 八个**。

---

## ③ 第二件的落地：spec §13

### ③.1 ⚠️ 顶回 3 + 4：派单给的文件名与行尾属性都**不对**

**文件名**：派单写的是 `Document/2026-10-08-规格说明书-智慧体育分层运动处方系统.md`。
实测仓里**没有这个文件**（`Document/` 下只有 4 个 `.md` + 1 个 `.doc`）。
真正的 spec 是 **`Document/2026-09-28-体育闭环原型-设计spec.md`**，
而派单给的四个取证数与它**逐字吻合**（实测：`bytes=163922  CRLF=1229  bareLF=0
sha256[:16]=32329DD43DF6981C`），故认定是同一份、按它改。

**行尾属性**：派单说「spec 是 `text eol=lf` 钉死的（`.gitattributes`）」。实测**不是**：

```
git ls-files --eol -- Document/
i/lf    w/crlf  attr/      Document/2026-09-28-体育闭环原型-设计spec.md
                                        ^^^^^ attr 为空
```

`.gitattributes` 自己逐字写着「范围**只限 backend/data/**：本仓其余文档（计划文档、spec、
账本）当前是『index LF / 工作树 CRLF』」，`.superpowers/**` 用 `-text`，
`Document/**` **两条都没覆盖**；它的「index LF / 工作树 CRLF」是 `core.autocrlf=true`
（实测 `git config core.autocrlf` → `true`）得来的。
⚠️ 故本次改写**整段以 CRLF 写入**（`read_bytes()` 量、`write_bytes()` 写），
`git diff --stat` 只有 **109 插入 / 16 删除**（不是整文件重写）。
若照派单那句以 LF 写，工作树会变成一个与「一次 fresh checkout」不同的形状。

### ③.2 §13 改前 → 改后（要点对照）

改前 §13 是 **30 行 / 904 B**（Plan 01 时期的四条命令 + 一个 bash 代码块 + 两句尾注）；
改后是 **123 行 / 7 611 B**，拆成 6 个小节：

| 改前 | 改后 |
| --- | --- |
| `python -m venv .venv && .venv\Scripts\activate` + `pip install -e ".[dev]"` | §13.2 保留安装那一步，并注明本机实测环境是 **Python 3.11.1、无 venv**（用虚拟环境也可以） |
| `python -m app.seed.generate --students 500 --weeks 16 --seed 20250828` | **删掉**。改推 §13.1 的 `backend\scripts\demo.ps1`：一条命令 = 删旧演示库 → 灌一学期数据 → 跑**两次**每日批处理 → **复核禁区** → 起 uvicorn；参数 `-Port 8010` / `-Students 60` / `-Seed 20250828` / `-DryRun`。⚠️ 明写它写的是 `pe_demo.db` **不是** `pe.db`，CSV 落 `$env:TEMP`、**一个字节都不进 `backend/data/`** |
| `python -m app.pipeline.backfill --semester 2025-2026-1` | 移进 §13.3 的**警告**里。尾注那句「`backfill` 是原型的关键能力」保留，但补上「`demo_bootstrap.py` **刻意不调它**」及其理由（回放要跑一学期的每一天，演示只需要「今天」这一个切片，两次 `run_daily` 就够） |
| `python -m app.pipeline.daily --semester … --date …` | 同上 |
| （无） | §13.3 **明确警告三个 CLI**（`app.seed.generate` / `app.pipeline.backfill` / `app.pipeline.daily`）的 `main()` 把缺省值写死在 **`backend/data/seed/`** 与 **`backend/pe.db`** 两个禁区上，故**开发时不要用**；要用就**必须**显式传 `--csv-dir` 与 `--db-url`（并点名 `demo_bootstrap.py` 自带的两道前置守卫） |
| `uvicorn app.main:app --reload --port 8000` | §13.2：`cd backend` → **必须显式设 `PE_DB_URL`**（⚠️ `app.config.DEFAULT_DB_URL` 逐字指向禁区 `pe.db`，而 lifespan 里的 `init_db` 会 `create_all`，不设就当场建出那个文件）→ 要用 `POST /api/pipeline/run-daily` 还得设 `PE_CSV_DIR`（缺省值是恒为 0 文件的 `backend/data/seed/`）→ `python -m uvicorn app.main:app --port 8000` |
| （无） | §13.4 **两个身份头**：`X-Student-Id`（整数；缺头 401 / 不在册 403 / 不是整数 422）与 `X-Teacher-Staff-No`（字符串；缺头或空白 401 / 不在册 403）。两者已注册成 OpenAPI 的 `apiKey` securityScheme，故 `/docs` 上有 **Authorize** 按钮。⚠️ **9 个可写资源的 POST/PATCH/DELETE 一律要教师头**（逐个点名；匿名写 **401**；`semesters` 无 DELETE 故 26 个操作而不是 27）。⚠️ **读的一侧一律匿名**，故**没有**「登录后才能看」这一档。⚠️ **口令不在任何匿名响应里**：教师走 `GET /api/class-sessions/{id}/rpe-token`，学生端的口令只能来自课堂投屏 |
| （无） | §13.5 **`/docs`、`/openapi.json`（Plan 04 前端 codegen 的输入）、`/api/health`** 三个地址；⚠️ 数端点一律用 `app.openapi()["paths"]`、**不要用 `len(app.routes)`**（惰性 include，实测只有 6）；结案口径 **64** 路径模板 / **92** 操作 / **45** 挂 `security` |
| `cd frontend; npm install && npm run dev` + 两个 URL | §13.6 保留，并注明 **`frontend/` 在 Plan 03 结案时还不存在**（Plan 04 才建）；后端已开 CORS `allow_origins=["*"]` + `allow_headers=["*"]`（后者必需：两个自定义身份头会触发预检），⚠️ `allow_origins=["*"]` 是原型口径、**上线前必须收紧** |
| 「**登录**：预置账号 + 角色切换器（学生 / 教师 / 管理员各若干），不做注册流程。」 | 保留原话但如实标注：原型阶段落地为「前端自己存一个身份、按它发那两个头」，**没有**「登录后才能看」这一档 |
| （无） | 节首一段 blockquote 说明**本节为什么整体改写**（与本仓既有的「勘误（Ruling …）」体例一致） |

### ③.3 spec 的行尾与字节数取证

| 项 | 改前（= 派单给的 Task 9 结案数，实测吻合） | 改后 |
| --- | --- | --- |
| 字节数 | 163 922 B | **170 629 B** |
| 行数（`read_bytes().count(b"\n")`） | 1229 | **1322** |
| CRLF 计数 | 1229 | **1322** |
| 裸 LF | 0 | **0** |
| 裸 CR | 0 | **0** |
| BOM | 无 | **无** |
| sha256[:16] | `32329DD43DF6981C` | **`042250572DEB0394`** |

⚠️ 派单说「1230 行」，实测按 `\n` 计数是 **1229**（文件以 CRLF 结尾，故没有第 1230 行）。
差一格是派单的口径，不是本波改出来的。改后同口径是 **1322**（若按派单那种数法是 1323）。

⚠️ **改前先备份**（`Copy-Item` 到 `$env:TEMP\spec_backup_before13.md`），
且**不用 `git checkout` 还原**（`core.autocrlf=true` 会按属性重写工作树，硬规矩 #46/#70）。

⚠️ 定位 §13 用 `Grep` + 定长 Read，**没有 Read 整个 spec**（163 922 B）。
替换用 python 的 `text.index("## 13. 运行方式")` / `text.index("## 14. 待确认事项清单")`
两个锚点 + 断言 `old_block.endswith("---\r\n\r\n")`，故 §13 之外一个字节没动
（`git diff --stat` 只有那一个文件、109/16）。

**亲验**：`powershell -ExecutionPolicy Bypass -File backend\scripts\demo.ps1 -DryRun` 跑通
（60 人；25 张表都有行：prescription 60 / class_session 8 / rpe_record 240 /
training_log 840 / mini_test 180 / alert 30 / notification 19 / weekly_class_report 5；
两次 `run_daily`），脚本末尾自报
「禁区复核：backend\pe.db 不存在、backend\data\seed\ 仍为 0 文件 ✓」并把 TEMP 工作目录删掉。
**故 §13.1 里那条命令是真的能跑的，不是照着脚本源码猜的。**

### ③.4 ⚠️ 顶回 5：全仓 `seed.generate` 命中清单（逐条标注）

派单点名的三处候选**全部落空**：README **不存在**（仓库根与 `backend/` 都没有）、
`frontend/` **不存在**、`pyproject.toml` **没有** `[project.scripts]`、
`app/main.py` 那一处是**正确的提及**。真正「教人照它跑」的是**另外三处**，
全靠全仓 grep 才找到（第 3 处是在前两处改完、重跑 grep 时才发现的）。

`git grep -n "seed.generate"` 全仓 **525** 行命中，分布在 **149** 个文件：
**93** 行 / **38** 个文件在 `.superpowers/` 之外，**432** 行 / **111** 个文件在 `.superpowers/` 里。

**分类口径**（硬规矩 #109：分清「它本身」与「对它的提及」）：

* **A = 正确的提及**（描述它存在 / 引用它作符号 / 解释为什么**不**用它）——不动
* **B = 教人照它跑**——**本波改掉**
* **C = 历史审计链**（`.superpowers/**`）——不动（改了就是篡改历史取证）
* **D = 历史计划文档**（`Document/2026-*-实施计划0X-*.md`）——不动（它们是那三个 Plan
  自己的 Interfaces / 禁区纪律 / 验收清单，是**当时的**事实）
* **E = spec §13 本身**——本波改

**B 类（3 处，全部改掉）**：

| 住址 | 改前逐字 | 为什么是 B | 改后 |
| --- | --- | --- | --- |
| `backend/app/db/session.py::init_db` 的 docstring | 「已有的 `backend/pe.db` **必须删掉重新跑** `python -m app.seed.generate`」 | 一句话教人破**两个**禁区（跑禁区 CLI + 删/重建禁区文件），而它住在「schema 改动 = 重建库」这条纪律的**唯一住址**上，下一个人一定会读到 | 「必须**删掉库文件重灌**；重建库请走 `backend/scripts/demo.ps1`；确实要用那三个 CLI 就**必须**显式传 `--db-url` 与 `--csv-dir`」，并把「两个 CLI 都没有 `--recreate` 开关」按实际写成「那些 CLI」 |
| `backend/app/db/models/__init__.py` 的模块 docstring | 「本地已经生成过库的人，改完 schema **必须删掉 `pe.db` 重跑** `python -m app.seed.generate`」 | 与上一处**同形**（同一个失效说了两遍），且它下面 3 行就已经在讲 `pe_demo.db` 与「`pe.db` 是禁区」，**前后自相矛盾** | 「必须**删掉库文件重灌**；重建库请走 `demo.ps1`；要用那三个 CLI 就必须显式传 `--db-url` 与 `--csv-dir`」，并指回 spec §13.3 与 `init_db` 的 docstring |
| `backend/app/demo_data.py::_semester_of` 的**运行时报错消息** | 「先跑 app.seed.generate.seed_database（它按 app.seed.config.SEMESTERS 建学期），或者把 as_of 挪进学期区间」 | 它指的是**函数**（要显式传 `session`，碰不到禁区），但措辞是「先**跑** X」，而读到它的人正好是刚撞上一次失败灌数据的人——最容易顺手敲成 `python -m app.seed.generate` | 「先**调** app.seed.generate.seed_database（⚠️ 是**调函数**、不是跑 `python -m app.seed.generate` —— 那个 CLI 的缺省值写死在 `backend/data/seed/` 与 `backend/pe.db` 两个禁区上，演示请走 `backend/scripts/demo.ps1`），或者把 as_of 挪进学期区间」 |

**E 类（1 处）**：`Document/2026-09-28-体育闭环原型-设计spec.md` §13 —— 见 §③.2。
改后 spec 里仍有 **3** 行含 `app.seed.generate`，三行**全是警告或语义说明**
（§13 节首 blockquote 的「其中 `python -m app.seed.generate` 会把两个禁区写出来」、
§13.1 的「`pe.db` 的语义是『`app.seed.generate` 写出来的那份不可复现的库』」、
§13.3 的「这三个 CLI 都存在、都能跑，但缺省值写死在两个禁区上」），**没有一行教人跑它**。

**A 类（34 个文件 / 87 行，逐条核过，全部不动）**：

| 文件 | 行 | 判定 |
| --- | --- | --- |
| `.gitignore` | 1 | A —— 解释 `pe.db` 那条忽略规则的**语义** |
| `backend/app/config.py` | 3 | A —— 「`DEFAULT_CSV_DIR` 是 `python -m app.seed.generate` 写三类 CSV 的缺省目录」＋两处「这个常量此前住在 `app/seed/generate.py`」的搬家史 |
| `backend/app/db/session.py` | 2（余） | A —— `engine()` 的 docstring 里「三个 CLI 都已经显式传 `DEFAULT_DB_URL`」（描述事实）＋「生产调用点只有 3 处（`app/seed/generate.py` …）」 |
| `backend/app/demo_data.py` | 1（余） | A —— 就是上面 B 那处改后留下的「⚠️ 是调函数、不是跑那个 CLI」 |
| `backend/app/domain/indicators.py` | 1 | A —— 「`app.seed.generate` 的那句导入都照旧可用，一个字都没改」（兼容性说明） |
| `backend/app/main.py` | 1 | A —— `DEMO_DB_URL` 的注释：「`pe.db` 的语义是『`app.seed.generate` 写出来的那份不可复现的库』」。⚠️ **派单点名的候选之一，实测是正确的提及**（`app/main.py:4` 那句「Plan 01/02 交付的是一个批处理系统（`python -m app.pipeline.daily`）」也是 A：它在讲历史，不是教人跑） |
| `backend/app/pipeline/backfill.py` | 2 | A —— 那**两个 CLI 自己的** `main()` docstring：「`--db` 缺省取 `DEFAULT_DB_URL`，与 `python -m app.seed.generate` 同」＋搬家史 |
| `backend/app/pipeline/clean.py` | 1 | A —— 兼容性说明 |
| `backend/app/pipeline/daily.py` | 2 | A —— 一处是 `semester_by_name` 报错消息里的「（组织结构由 python -m app.seed.generate 建立）」：它**陈述来源**、不叫人跑，而且能读到它的人**已经在跑那三个 CLI 之一**；另一处是该 CLI 自己的 `main()` docstring |
| `backend/app/pipeline/run_stratify.py` | 5 | A —— 全是 `:func:`app.seed.generate.build_dataset`` 一类的**符号引用**与搬家史 |
| `backend/app/refdata.py` | 1 | A —— 搬家史 |
| `backend/app/seed/**`（`config.py` 2 / `fitness.py` 4 / `generate.py` 2 / `sections.py` 1） | 9 | A —— **它自己**（`generate.py` 那 2 行是 `main()` 的 docstring 与 `argparse` 的 `prog=`）。⚠️ 硬规矩 #109 的教科书案例：「它本身」不是「教人照它跑」 |
| `backend/scripts/demo.ps1` | 2 | A —— **派单逐字点名不要改**：它在解释「为什么本脚本一条 `python -m …` 都没有」 |
| `backend/scripts/demo_bootstrap.py` | 2 | A —— 同上（模块 docstring 第 12-13 行逐字是「本仓有三个 CLI 入口……而它们的 `main()` 各自把缺省值写死在**禁区**上」）＋一行 `from app.seed.generate import …`（**调函数**、显式传路径） |
| `backend/tests/**`（14 个文件 / 30 行） | 30 | A —— 全是 `from app.seed.generate import build_dataset/seed_database/write_csv`（测试**调函数**灌内存库或 `tmp_path`，碰不到禁区）＋ `tests/architecture/` 那 20 行**字符串字面量**（它们测的是 `resolve_name` 的相对导入解析，`"app.seed.generate"` 只是一个被解析的串）＋ `test_refdata_prescription.py` 那 2 行「**绝不跑** `python -m app.seed.generate` 一类的 CLI」＋ `tests/api/conftest.py` 那 1 行语义说明 |

**C 类**：`.superpowers/**` **111 个文件 / 432 行**——账本、简报、实现者报告、评审包、
取证探针。它们是**历史取证**（里面大量互引自己的字节数与 sha256），
改一行就让整条审计链的数字变假。**一律不动。**

**D 类**：`Document/2026-09-28-实施计划01-*.md`（9 行）、
`Document/2026-10-06-实施计划02-*.md`（6 行）、`Document/2026-10-08-实施计划03-*.md`（2 行）。
⚠️ Plan 01 那 9 行里有 3 行**长得像**运行手册（`:756` 的「CLI：`python -m app.seed.generate
--students 500 …`」、`:2509-2510` 的两条命令、`:2588-2589` 的验收清单），
但它们分别是 **Plan 01 Task 5 的 Interfaces 规格**、**Task 8 的验收命令**与
**Plan 01 的交付物清单**——即「当时要建什么、怎么验它」，是**历史计划**、不是运行手册。
Plan 02/03 那 8 行**全是禁区纪律**（「**不要跑** `python -m app.seed.generate` / …」）。
**一律不动**；运行手册的唯一住址现在是 spec §13（已改）。

---

## ④ 待清扫 / 关切 / 没按派单做的地方 / 顶回

### ④.1 待清扫（**5** 条，全部移交 Plan 04，本波没动）

1. **`read_rpe_token` 只过「在册」闸门、不过任教关系闸门** → **任何在册教师可以读任何班的口令**。
   与本模块其它四个教师端点（`open-rpe` / `rpe-status` / `mini-tests/batch` /
   `mini-tests/normalized`）以及 `POST …/overrides` / `POST …/regenerate` /
   `POST …/alerts/{id}/handle` **同档**。收窄是一次一行的改动
   （`require_teacher` → `require_teaches_section`），但那会改掉 Plan 04 教师端的可点范围，
   故移交（终审已登记，本波把新端点**加进**那一份清单，`routers/feedback.py` 的
   模块 docstring 与 `read_rpe_token` 的「代价如实记录」一节都写了）。
   ⚠️ 本波把暴露面从「**任何人**」收窄到「**任何在册教师**」，是净改善，但**没有归零**。
2. **泛型 PATCH 仍能把 `rpe_opened` 单独翻上去/翻下去**（Task 3 刻意不加跨列校验）。
   翻**上去**得到 409（安全失败，既有口径）；翻**下去**得到「口令在库里但交不上来」——
   现在两个端点对那一档给**同一个** 409（守卫 ④ 第 ③ 拍钉住），
   但⚠️ **库里那一串口令变成了垃圾**，而**没有 API 能清掉它**
   （`rpe_token` 不在 `ClassSessionUpdate` 上，那是 I4 的成果、不该回退），
   只能再 `open-rpe` 一次覆盖掉。要根治得给「关闭快评」一个专门的操作端点。
3. **学生端无法从任何 API 拿到口令，只能读教师课堂投屏。** 这与 spec §8.1 一致
   （口令在课堂上投屏、学生手输），但⚠️ **Plan 04 的学生端 H5 必须做成「手输口令」
   而不是「自动带入」**。`PendingRpeRead` 的 docstring 已改（§②.8），
   但那要 Plan 04 的实现者读到它才算数——建议在 Plan 04 的简报里点名。
4. **`_LITERAL_TAILED_SPECIAL_ROUTES` 的 docstring 与它自己的内容有出入**：
   docstring 写的判据是「末段为字面量」，而清单里 3 项**全是三段**路径，
   `open-rpe` / `rpe-status` / `alerts/{id}/handle` / `notifications/{id}/read` /
   `students/{id}/home` / **本波新加的 `rpe-token`** 这些四段的字面末段特例路径
   **一个都不在列**。实际判据是「与泛型 `{path}/{pk}` **同形**」。本波没改它
   （改判据措辞是一次纯文档改动，而那份清单的**行为**是正确的）。
5. **`demo.ps1` 打印的示例 URL 串里没有新端点**（`GET …/rpe-token`）。
   不影响正确性（那只是演示提示），下一次动 `demo.ps1` 时可以顺手加一行。
   ⚠️ 本波**没有**改它：它是 UTF-8 带 BOM + CRLF（PowerShell 5.1 读无 BOM 的中文 `.ps1`
   会按 ANSI 静默乱码），而派单逐字说「`demo.ps1` 与 `demo_bootstrap.py` 里提到
   `seed.generate` 是正确的提及，不要改」。

**关切（不是待清扫，只是如实记录）**：`backend/pe_demo.db` 在开工时就存在
（上一次演示留下的），本波**没动它、也没删**（它不是禁区，且已进 `.gitignore`）。
`-DryRun` 那次亲验一律落在 `$env:TEMP` 并自删。

### ④.2 没按派单做的地方（**5** 处，全部有理由）

1. **多改了一处生产代码：`catalog.py` 加 `"list_exclude": ("rpe_token",)`。**
   派单没要求（它只说「把 `rpe_token` 从 `ClassSessionRead` 去掉」）。
   **不做的话洞没堵上**（§②.1）。
2. **多抽了一个私有谓词 `_rpe_is_open`**，并把 `open_rpe` 与 `submit_rpe` 里那两处
   既有字面量改成调它（各 1 行）。派单没要求，而「不 refactor 周边代码」是默认纪律。
   理由：新端点**必须**用与 `submit_rpe` 逐字相同的判据（§②.4），
   而抄第三份就是第三个所有者；本仓对「一件事只有一个住址」的要求高于「不动周边」。
   ⚠️ 这是**行为等价**的改动（守卫 ④ 第 ③ 拍 + 既有的
   `test_submitting_to_a_session_that_was_never_opened_is_409` 都绿）。
3. **多改了 4 处文档**（`PendingRpeRead` / `ClassSessionCreate` / `open_rpe` 的旧谓词字面量 /
   `catalog.py` 与 `crud.py` 与 `test_crud.py` 里「23 行没有一行用 `list_exclude`」那三句
   已过期断言）。派单没点名，但**不改就是把 Plan 04 指向错误的门**（I4 批评的正是这个）。
4. **没有把新路径加进 `_LITERAL_TAILED_SPECIAL_ROUTES`**（派单第 3 条只要求「自己实测确认」，
   我实测确认了、并说明为什么不加：§②.5 末）。
5. **commit ② 做过一次 `--amend`**（把第三处 B 类修正折进去，并把标题「两处」改成「三处」）。
   分支**没有 push**，故 amend 是安全的；不 amend 的话要么多一个 commit（超出建议的 2-3 个），
   要么把一处代码修正混进「报告」那个 commit 里。

⚠️ 除此之外**逐字照派单做**：分支名、不 push、不碰 main、探针放 `$env:TEMP`、
写文件走 python、`git add` 逐个文件名、commit 信息走 UTF-8 无 BOM 临时文件 + `git commit -F`、
端点计数走 `openapi()["paths"]`、行尾/BOM 改前改后都用 `read_bytes()` 量。

### ④.3 顶回控制者的地方（**5** 处）

| # | 顶回 | 级别 | 处置 |
| --- | --- | --- | --- |
| 1 | **派单第 1 条第 1 步不足以堵住它自己点名的那个洞**：泛型 list 端点不走 `response_model`，故只摘 `ClassSessionRead` 之后 `GET /api/class-sessions` 照旧返回全部口令。照派单字面做完会 **1251 全绿而洞原样留着** | **Critical** | 顶回并**补做**：`catalog.py` 加 `list_exclude`，守卫 ① 断 list 的响应体、遍历守卫加两拍。**是守卫 ① 当场红了才发现的**——这也说明派单要求的「匿名 GET 的响应里没有 `rpe_token` 这个键」那一拍，只有落在 **list** 上才有牙 |
| 2 | **控制者给方案 (b) 的理由与实现不符**：派单说方案 (a)「重新 `open-rpe` 会生成**新**口令，学生手上那个就废了」。实测 `open_rpe` 幂等**且第二次不换口令**（`already_open = _rpe_is_open(row)`；`if not already_open:` 才生成），既有守卫 `test_open_rpe_twice_keeps_the_first_token` 逐字钉着这件事。故 (a) 拿到的是**同一个串**，那个 UX 后果不会发生 | 中 | **结论仍然选 (b)**（我照做了），但**理由换成语义**：(a) 要拿一个 `POST`（「发起」这个动作）当读操作使，前端还得靠 `already_open` 反推「其实什么都没发生」；(b) 是一个 `GET`，说的就是做的。据实改写进 `ClassSessionRead` 的 docstring（含「实现者据实更正」那句话） |
| 3 | **派单给的 spec 文件名不存在**（`Document/2026-10-08-规格说明书-智慧体育分层运动处方系统.md`）。真正的 spec 是 `Document/2026-09-28-体育闭环原型-设计spec.md`；认定依据是派单给的四个取证数与它**逐字吻合** | 低（事实更正） | 按真名改，并在 §13 的 commit 信息里写明认定依据 |
| 4 | **派单说「spec 是 `text eol=lf` 钉死的（`.gitattributes`）」——实测不是**：`git ls-files --eol` 报 `i/lf w/crlf attr/`（attr 为空），`.gitattributes` 自己逐字写着「范围**只限 backend/data/**」 | 低（事实更正，但**会影响做法**） | 整段以 **CRLF** 写入工作树；若照派单以 LF 写，工作树会变成与「一次 fresh checkout」不同的形状 |
| 5 | **派单点名的三处候选全部落空**（README 不存在、`frontend/` 不存在、`pyproject.toml` 没有 `[project.scripts]`、`app/main.py` 那一处是正确的提及），而真正「教人照它跑」的是**另外三处**（`db/session.py`、`db/models/__init__.py`、`demo_data.py`），其中第 3 处是在前两处改完、重跑 grep 时才发现的 | 中 | 全仓 grep（525 行 / 149 文件）逐条分类，见 §③.4；三处 B 类全部改掉 |

⚠️ **顶回 1 是这一波最要紧的一条**：它与 Plan 02/03 那 75 次顶回是同一个形状
——控制者对着「文档的形状」推理（「`rpe_token` 在 `ClassSessionRead` 上，摘掉它就行」），
实现者对着「守卫实际能抓到什么」推理（「list 端点压根不经过那个模型，
而既有守卫还把 list 的键集合钉成**比 read-one 多**」）。

---

## ⑤ 最终验收

| 项 | 基线 | 本波结案 | 判定 |
| --- | --- | --- | --- |
| `python -m pytest -q` | 1251 passed | **1255 passed**（142.92 s） | ✅ +4（四条新守卫） |
| `--cov=app.domain --cov-branch` | 1268 / 0 / 376 / 0 / 100% | **1268 / 0 / 376 / 0 / 100%** | ✅ **四格逐字不变**（本波一个字节都没动 `app/domain/`） |
| 带 `--cov` 时的通过数 | 1250 passed, 1 skipped | **1254 passed, 1 skipped**（268.51 s） | ✅ |
| 表数 | 25 | **25** | ✅ |
| 架构扫描面 | 60 | **60** | ✅（没有新增/删除 `.py`；探针一律放 `$env:TEMP`，硬规矩 #108） |
| `/api/` 路径模板 / 操作 | 63 / 91 | **64 / 92** | ✅ +1 路径 / +1 操作（新端点是一个新路径模板上的一个 GET） |
| 挂 `security` 的操作 | 44 | **45** | ✅ 19 特例 + 26 CRUD 写入 |
| `len(app.routes)`（假绿参考） | 6 | **6** | ⚠️ 全程不用它计数 |
| `_MODELS_PUBLIC_BASELINE` | 33 | **33**（未动；由既有守卫钉住，1255 全绿即证） | ✅ |
| 14 个黄金用例 | 14 | **14**（`tests/integration/test_golden_cases.py` 全绿） | ✅ |
| 指纹 ①`national_standard_2014.csv` | `D2C8E539E2FA0029` | `D2C8E539E2FA0029` | ✅ |
| 指纹 ②`exercises.yaml` | `5394B37F01DAC9AC` | `5394B37F01DAC9AC` | ✅ |
| 指纹 ③`exercise_equivalence.yaml` | `822CB86A5E998301` | `822CB86A5E998301` | ✅ |
| 指纹 ④`alert_rules.yaml` | `E48E3AC82BB45BB7` | `E48E3AC82BB45BB7` | ✅ |
| 指纹 ⑤ 18 套处方模板 | 18 个 / 123 848 B | **18 个 / 123 848 B**（合计 `83DA02814A29679C`） | ✅ |
| `backend/data/**` 全量 | 24 文件 / `DD64C37D7D48057B` | **24 文件 / `DD64C37D7D48057B`** | ✅ 一个字节没动 |
| `git diff 9c540d5 HEAD -- backend/data` | —— | **空** | ✅ |
| `backend/pe.db` | 不得存在 | **exists: False** | ✅ |
| `backend/data/seed/` | 0 文件 | **0 文件** | ✅ |
| spec | 163 922 B / 1229 CRLF / `32329DD43DF6981C` | **170 629 B / 1322 CRLF / 裸 LF 0 / 裸 CR 0 / 无 BOM / `042250572DEB0394`** | ✅ |
| `git status --short`（结案时） | —— | **空**（工作树干净） | ✅ |

**本波改动的 12 个文件**（`git diff --name-only 9c540d5 HEAD` + 本报告）：

```
Document/2026-09-28-体育闭环原型-设计spec.md          ← §13 整体改写
backend/app/api/crud.py                               ← list_exclude 的 docstring（「23 行没有一行用它」已过期）
backend/app/api/routers/catalog.py                    ← +list_exclude=("rpe_token",) ＋模块 docstring 更正
backend/app/api/routers/feedback.py                   ← +read_rpe_token ＋_rpe_is_open ＋docstring 计数
backend/app/api/schemas/dashboard.py                  ← PendingRpeRead 指向错误门的更正
backend/app/api/schemas/feedback.py                   ← ClassSessionRead 7→6 列 ＋RpeTokenRead
backend/app/db/models/__init__.py                     ← B 类第 2 处
backend/app/db/session.py                             ← B 类第 1 处
backend/app/demo_data.py                              ← B 类第 3 处
backend/tests/api/test_crud.py                        ← 第二份清单 ＋对齐断言 ＋遍历守卫三拍
backend/tests/api/test_feedback.py                    ← 四条新守卫
backend/tests/api/test_prescription_api.py            ← expected 18→19、44→45
```

**行尾与 BOM 复核**（改前改后都用 `read_bytes()` 量；全部**纯 CRLF、裸 LF 0、无 BOM**，
与开工时逐字同档）：`schemas/feedback.py` 585→655 CRLF、`schemas/dashboard.py` 402→407、
`routers/feedback.py` 877→1023、`routers/catalog.py` 496→517、`api/crud.py` 774、
`db/session.py` 100、`demo_data.py` 499、`db/models/__init__.py` 148→153、
`test_crud.py` 2138→2242、`test_feedback.py` 1450→1693、`test_prescription_api.py` 1630→1649。
spec 是 1229→1322 CRLF（裸 LF 恒 0）。
⚠️ 中途踩过一次编辑工具把两行缩进弄乱、并把「**已经建出来了**」重复了一次的坑，
用 python 字节级替换修回来了（改后 `py_compile` 通过、`CRLF=1013 bareLF=0`）。

**探针残留**：全部探针写在 `$env:TEMP`（`pe_probe_baseline.py` / `pe_probe_forbidden.py` /
`pe_probe_eol.py` / `pe_probe_hits.py` / `pe_fix_*.py` / `pe_commit*.py` /
`spec_backup_before13.md`），**仓库里一个都没留**，跑完删掉（硬规矩 #108：
架构守卫会 AST 解析工作树里的全部 `.py`，含未入库的）。

---

## ⑥ commit sha

| # | sha | 主题 | 文件数 |
| --- | --- | --- | --- |
| ① | `3078a4d` | `fix(api): rpe_token 不再匿名可读 —— 摘读模型 + 排 list + 教师端窄读门` | 8（+662 / −48） |
| ② | `9b49a5e` | `docs(spec): §13「运行方式」按 Plan 03 之后的实际改写 + 扫掉三处「教人照禁区 CLI 跑」` | 4（+133 / −26） |
| ③ | *本文件所在的那个 commit*（⚠️ 它的 sha 写不进它自己：写进去再 commit 就换了 sha，故在交回控制者的消息里给） | `docs(sdd): Plan03 收尾小修波结案报告` | 1 |

⚠️ commit ② 做过一次 `--amend`（sha 从 `d563e43` → `7428251` → **`9b49a5e`**）：
先折进第三处 B 类修正，再把标题的「两处」改成「三处」。分支**没有 push**，故 amend 安全。

**分支** `fix/rpe-token-and-spec13`，起点 `9c540d5`（`main`）。
**没有 push、没有 fast-forward、没有碰 `main`**——合并由控制者做。
