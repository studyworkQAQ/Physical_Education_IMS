"""Plan 03 Task 3 结案：账本追加 Ruling 9（顶回 7 处采纳 + 控制者错误 #7-#12）。"""
from pathlib import Path

P = Path(__file__).with_name("progress.md")
b = P.read_bytes()
t = b.decode("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
print(f"[before] bytes={len(b)} lines={t.count(nl)}")

BODY = """

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

控制者的亲验探针用**文本计数**去核 `catalog.py` 的读写矩阵（`cat.count('writable=False')` / `cat.count('on_delete=\"restrict\"')` / `cat.count('build_crud_router(')`），实测得到 **0 / 0 / 1** —— 而实现者报的是 14 / 12 / 23。**原因是 `RESOURCES` 是一张数据驱动的表（一个列表），不是 23 处字面的 `build_crud_router(...)` 调用**，故文本计数天然数不到。
**这正是硬规矩 #89 逐字禁止的动作**（「数键/字段/成员一律用运行时口径，绝不用正则数源码」），而控制者**在同一个探针里同时用了两种口径**：OpenAPI 的运行时计数（对的，与实现者吻合）与文本计数（错的）。**→ 硬规矩 #89 第 5 次被违反（#139 / #147 / #155 / #6 / #12）。**
**处置**：**以 OpenAPI 口径为准**（POST 9 / PATCH 9 / DELETE 8，控制者独立跑出，与实现者的三个口径全部吻合），**文本计数的那三行结论作废、不写进任何裁定**。
**→ 补硬规矩 #103：一个探针里若同时有两种口径能回答同一个问题，以「运行时/结构化」那一种为准，并把另一种的输出**标注为不可用**而不是并列打印——并列打印会让读数的人（包括控制者自己）随手引用错的那一个。** 依据：#12。

**下一步**：抽 `task-4-brief.md` → 派实现者（处方侧的特例端点）。
"""

if nl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", nl)
SENT = "Task 3: complete (commits 40a7a0e..e88afaf"
assert SENT not in t, f"{SENT!r} 已存在"
P.write_bytes((t.rstrip("\r\n") + BODY).encode("utf-8"))
c = P.read_bytes().decode("utf-8")
print(f"[after]  bytes={len(c.encode('utf-8'))} lines={c.count(nl)}")
for k in ("Ruling 9", "硬规矩 #103", "控制者错误 #7", "控制者错误 #12", "876 passed", "38 次"):
    print(f"  {k}: {c.count(k)}")
