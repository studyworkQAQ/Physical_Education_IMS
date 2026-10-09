"""Plan 03 Task 4 预检更正（P4-A1..A7）+ 账本 Ruling 10。逐条 assert 命中次数。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAN = ROOT / "Document" / "2026-10-08-实施计划03-反馈预警与CRUD-API层.md"
LEDGER = HERE / "progress.md"
edits = []


def patch(path, pairs):
    raw = path.read_bytes()
    t = raw.decode("utf-8")
    nl = "\r\n" if "\r\n" in t else "\n"
    b0 = (len(raw), t.count(nl))
    for old, new, count, label in pairs:
        if nl != "\n":
            old = old.replace("\r\n", "\n").replace("\n", nl)
            new = new.replace("\r\n", "\n").replace("\n", nl)
        n = t.count(old)
        assert n == count, f"[{label}] 期望 {count}，实为 {n}\n  old={old[:90]!r}"
        t = t.replace(old, new)
        edits.append((label, n))
    path.write_bytes(t.encode("utf-8"))
    c = path.read_bytes().decode("utf-8")
    print(f"[{path.name}] {b0[0]} B / {b0[1]} 行 -> {len(c.encode('utf-8'))} B / {c.count(nl)} 行")


PRE = """
### ⚠️ 预检更正（Pre-flight，控制者亲跑于 `e2a0803` + 一次**真实 HTTP 冒烟**，取证脚本 `t4_probes/_preflight.py` 与 `t3_probes/_live_smoke.py`）

**测试基线**：`876 passed`；`app/domain/` **996/0/288/0/100%**；**25 张表**（`prescription` **16 列**）；扫描面 **49**；**47 个 HTTP 端点已在线**（控制者起了 uvicorn、用 httpx 打了一整圈真实 CRUD）。

| # | 级别 | 事实（全部实测） | 更正 |
|---|---|---|---|
| **P4-A1** | **Critical** | **`WeeklySheet` 不能直接 JSON 化**：`json.dumps(dataclasses.asdict(sheet))` 抛 **`TypeError: cannot pickle 'mappingproxy' object`**（`AssembledBlock.structure` 是只读映射，`asdict` 会 `deepcopy` 它）。**带不带 `default=str` 都失败**——`default` 只在「未知类型」时被调用，而 `asdict` 在**到达 json 之前**就炸了。 | **不许用 `dataclasses.asdict`。** ⚠️ **Plan 02 已经解决过同一个问题**：`app.pipeline.prescription_stage.training_package_payload(pkg) -> dict` 就是「`TrainingPackage` → 可 JSON 的 dict」的投影，且它已经在 `prescription_stage.__all__` 里。**Task 4 的 weekly-sheet 投影必须建立在它之上（单一所有者），不得另写一份平行的投影。** 具体口径见下方「P4-A1 的落地口径」 |
| **P4-A2** | Important | **`weekly_factors_of` 已经存在**（Plan 02 Task 8 交付）：实测签名 `weekly_factors_of(session, prescription_id: int) -> list[WeeklyFactor]`，且在 `prescription_stage.__all__` 里。`WeeklyFactor` 的 4 个字段 = `week:int / factor:float / reason:str / source:str`。 | 计划 Task 8 说要「加 `weekly_factors_of`」是**过期的**（那是 Plan 02 的活，已交付）。**Task 4 直接调用它**，Task 8 只消费。**⚠️ 硬规矩 #91：派单里提到的每一条既有能力，先 `git grep` / `inspect.signature` 核实它存在** |
| **P4-A3** | Important | **`OverrideRecord` 的 7 个字段全部无缺省**：`kind: OverrideKind` / `target: str \\| None` / `old_value: str` / `new_value: str` / `reason: str` / `teacher_staff_no: str` / `applied_at: dt.datetime`。`OverrideKind` 的 5 个值实测 = `weekly_frequency` / `substitute_exercise` / `intensity_step` / `volume_scale` / `pause`（**下划线，不是连字符**）。`apply_overrides(pkg, records, *, exercises)` —— **`exercises` 是关键字必填**（Plan 02 的顶回 2）。 | **API 的请求模型必须是 5 个字段的另一个 Pydantic 类**（`kind` / `target` / `old_value` / `new_value` / `reason`），**`teacher_staff_no` 从身份头填、`applied_at` 从服务端时钟填**。⚠️ `kind` 的值域**直接引 `OverrideKind`**（`Literal` 或 Pydantic 的 enum 支持），**不要在 schema 里抄第二份字符串**（单一所有者）。⚠️ 调 `apply_overrides` 时**必须传 `exercises=`**，否则 `SUBSTITUTE_EXERCISE` 会留下旧动作的视频 URL —— 那是 Plan 02 顶回 2 逐字说的「一个看起来正常的谎」 |
| **P4-A4** | Important | `prescription` 实测 **16 列**，其中 `teacher_overrides` 是 **`TEXT NOT NULL`**（`JsonText`），`label_at_generation VARCHAR(20) NOT NULL` 也在（Plan 02 Task 7 fr1 加的）。 | 「追加一条覆盖」= **读 JSON 列表 → append → 写回**，而**不是** INSERT。**⚠️ 列是 NOT NULL**，故空列表要写成 `[]` 而不是 `NULL`。**顺序承重**（Plan 02 的 5.4：多条覆盖同一目标由**列表顺序**决定、后者胜）→ **不要按 `applied_at` 重排序** |
| **P4-A5** | Important | **前后端对接缺口 1**：实测 `openapi()["components"]` 里**没有 `securitySchemes`**、spec 顶层**没有 `security`**、47 个路径里**声明过的 header 参数为空**。而 `X-Student-Id` / `X-Teacher-Staff-No` 是全部学生侧端点的必需头。 | **本 Task 建第一个 `scope` 端点时，把这两个头注册成 OpenAPI 的 `apiKey` securityScheme**（`in: header`），并在需要它们的端点上挂 `dependencies=[Security(...)]`。**理由：不注册的话 Swagger UI 上没有地方能填它们、生成的 TS 客户端也不知道要发** —— 前端一接就撞 401 且不知道为什么。**⚠️ 用户 2026-10-08 明确要求「要确保后端和前端能够对接的上」，这一条是它的落点** |
| **P4-A6** | Important | **前后端对接缺口 3**：实测 **23 个 detail 路径的 path 参数名 distinct = `['pk_value']`**（`/api/semesters/{pk_value}`）。而 `build_crud_router` 的签名里**只有 `pk: str = 'id'`（DB 列名），没有给 OpenAPI 路径参数另起名的口子**。 | **给 `build_crud_router` 加一个 `pk_alias: str | None = None`**：`None` → 自动取**资源路径的单数 + 下划线**（`semesters` → `semester_id`、`course-sections` → `course_section_id`、`fitness-test-results` → `fitness_test_result_id`），显式传则覆盖。**理由：生成的 TS 客户端里到处是 `pkValue` 而不是 `semesterId`，前端读起来很难受；而这个改名是纯 OpenAPI 层的，不动 DB、不动路由匹配。** ⚠️ **改完 23 个 detail 路径的 URL 模板会变**（`{pk_value}` → `{semester_id}` 等），**那条遍历型守卫测试要跟着改** |
| **P4-A7** | Minor | **前后端对接缺口 2**：实测 CORS 是 `allow_origins=["*"]` / `allow_methods=["*"]` / `allow_headers=["*"]`，**没有 `allow_credentials`** → 预检响应里 `access-control-allow-credentials` 为 `None`。（`main.py` 的 docstring 已明写「上线前两者都要收紧」✓） | **这是浏览器规范的硬约束**（`allow_origins=["*"]` 与 `allow_credentials=True` 不能并存），原型阶段**不修**。**但必须写进 Plan 04 的约束**：**前端不得用 cookie / `fetch(..., {credentials:'include'})`，身份只能走请求头。** 已按硬规矩 #86 记进本计划的「计划边界说明」 |

**P4-A1 的落地口径**：
- `weekly-sheet` 端点返回的 JSON 形状 = `{"week": int, "factor": float, "reasons": [str], "sources": [str], "paused": bool, "sessions": [...]}`，其中 `sessions` 的每个 block **必须是 `training_package_payload` 产出的同一个形状**（含 `volume_unit` 与 `sessions_per_week`）。
- **做法**：先看 `training_package_payload(pkg)` 今天怎么把 `TrainingPackage` 投影成 dict（它已经处理了 `structure` 那个只读映射、`weeks`/`sessions`/`blocks` 三层、以及 `hr_zone` 的元组→列表）。**weekly-sheet 的投影 = 复用它的 block 级投影 + 换掉最外层**（`TrainingPackage` 的 `weeks` 换成 `WeeklySheet` 的 `week`/`factor`/`reasons`/`sources`/`paused`）。
- **若 `training_package_payload` 的 block 级投影是一个内嵌的私有函数**（很可能，因为它要递归三层），**把它提出来成一个模块级的 `_block_payload(block) -> dict`**，两处共用。⚠️ **这是「提取」不是「复制」**——复制会产生第二个所有者，而两个投影一旦漂移，前端在学生端看到的 block 与教师端看到的就不是同一个形状了。
- **要有一条测试钉住「weekly-sheet 里的 block 与 training_package_payload 里的 block 逐字段同形」**（用同一个包、同一周，比对两边的 block dict）。**这条测试是「两个投影不漂移」的唯一守卫。**

"""

patch(PLAN, [
    ("## Task 4: 处方侧的特例端点（教师覆盖 + 本周训练单 + 手动重生成）\n\n**Files:**",
     "## Task 4: 处方侧的特例端点（教师覆盖 + 本周训练单 + 手动重生成）\n" + PRE + "\n**Files:**",
     1, "P4 插入预检更正总表"),

    # Files 行：加 crud.py（pk_alias）与 main.py（securitySchemes）
    ("**Files:** Create `backend/app/api/routers/prescription.py`、`backend/tests/api/test_prescription_api.py`；"
     "Modify **`backend/app/api/schemas/prescription.py`（⚠️ S7：它由 Task 3 创建，本 Task 只补特例模型，"
     "原正文写「Create」会让人犹豫要不要覆盖）**、`backend/app/api/routers/__init__.py`",
     "**Files:** Create `backend/app/api/routers/prescription.py`、`backend/tests/api/test_prescription_api.py`；"
     "Modify **`backend/app/api/schemas/prescription.py`（⚠️ S7：它由 Task 3 创建，本 Task 只补特例模型）**、"
     "`backend/app/api/routers/__init__.py`（**⚠️ 新 router 挂这里，不是 `main.py`**——`main.py` 的注释逐字写着"
     "「只 include 这**一个**汇总路由：Task 5/7/8/9 各加一个 router 时改的是 `app/api/routers/__init__.py`，"
     "不是本文件（本文件压着 `pe.db` 禁区那条纪律）」）、"
     "**`backend/app/api/crud.py`（P4-A6：加 `pk_alias` 参数）**、"
     "**`backend/app/api/deps.py`（P4-A5：两个身份头注册成 OpenAPI 的 `apiKey` securityScheme）**、"
     "**`backend/app/pipeline/prescription_stage.py`（P4-A1：把 block 级投影提成模块级函数，供两处共用）**、"
     "`backend/tests/api/test_crud.py`（**P4-A6 改完 23 个 detail 路径的 URL 模板会变，遍历型守卫要跟着改**）",
     1, "P4-A1/A5/A6 Files 行"),

    # weekly-sheet 的投影口径（P4-A1）
    ("  - `GET /api/students/{student_id}/weekly-sheet?as_of=YYYY-MM-DD` → **spec §8.4 的「本周训练单」**："
     "调 `prescription_stage.weekly_factors_of` + `weekly.weekly_training_sheet`，返回 `WeeklySheet` 的 JSON 投影"
     "（`week` / `factor` / `reasons` / `sources` / `paused` / `sessions[].blocks[]`，**每个 block 带 `volume_unit`**）",
     "  - `GET /api/students/{student_id}/weekly-sheet?as_of=YYYY-MM-DD` → **spec §8.4 的「本周训练单」**："
     "调 `prescription_stage.weekly_factors_of`（**⚠️ P4-A2：它已经存在，Plan 02 Task 8 交付的，实测签名 "
     "`weekly_factors_of(session, prescription_id: int) -> list[WeeklyFactor]`，直接调用、不要重写**）"
     "+ `weekly.weekly_training_sheet`，返回 `WeeklySheet` 的 JSON 投影"
     "（`week` / `factor` / `reasons` / `sources` / `paused` / `sessions[].blocks[]`，**每个 block 带 `volume_unit`**）。"
     "**⚠️⚠️ P4-A1（Critical）：不许用 `dataclasses.asdict`** —— 实测它抛 "
     "`TypeError: cannot pickle 'mappingproxy' object`（`AssembledBlock.structure` 是只读映射，`asdict` 会 `deepcopy` 它），"
     "**带不带 `default=str` 都失败**（`default` 只在「未知类型」时被调用，而 `asdict` 在到达 json 之前就炸了）。"
     "**必须复用 Plan 02 已有的 `prescription_stage.training_package_payload(pkg) -> dict`**（它已经处理了只读映射、"
     "三层嵌套与 `hr_zone` 的元组→列表）：把它的 **block 级投影提成一个模块级函数**（如 `_block_payload(block) -> dict`），"
     "weekly-sheet 与 training-package 两处共用。**⚠️ 是「提取」不是「复制」**——复制会产生第二个所有者，"
     "而两个投影一旦漂移，前端在学生端看到的 block 与教师端看到的就不是同一个形状了。"
     "**要有一条测试钉住「weekly-sheet 里的 block 与 `training_package_payload` 里的 block 逐字段同形」**"
     "（同一个包、同一周，比对两边的 block dict）——**这条是两个投影不漂移的唯一守卫**",
     1, "P4-A1/A2 weekly-sheet 的投影"),

    # 教师覆盖的请求模型（P4-A3）
    ("  - `POST /api/prescriptions/{id}/overrides` → 教师覆盖。请求体是 `OverrideRecord` 的列表"
     "（**不含 `applied_at` 与 `teacher_staff_no`，那两个由服务端从时钟与身份头填**）；"
     "落进 `prescription.teacher_overrides`（`JsonText`）并返回覆盖后的 `TrainingPackage` 投影",
     "  - `POST /api/prescriptions/{id}/overrides` → 教师覆盖。**⚠️ P4-A3：请求体不能是 `OverrideRecord` 本身** —— "
     "实测它的 **7 个字段全部无缺省**（`kind` / `target` / `old_value` / `new_value` / `reason` / "
     "`teacher_staff_no` / `applied_at`），而**后两个必须由服务端填**（身份头 + 时钟），让客户端传等于让它能冒充别的教师、"
     "还能伪造时间。故**请求模型是一个 5 字段的 Pydantic 类**（`kind` / `target` / `old_value` / `new_value` / `reason`），"
     "端点补齐后两个再构造 `OverrideRecord`。⚠️ `kind` 的值域**直接引 `OverrideKind`**（实测 5 个值是 "
     "`weekly_frequency` / `substitute_exercise` / `intensity_step` / `volume_scale` / `pause`，**下划线不是连字符**），"
     "**不要在 schema 里抄第二份字符串**（单一所有者）。"
     "落进 `prescription.teacher_overrides`（**⚠️ P4-A4：这一列是 `TEXT NOT NULL` 的 `JsonText`**，"
     "故「追加一条覆盖」= **读 JSON 列表 → append → 写回**，不是 INSERT；空列表要写 `[]` 不是 `NULL`；"
     "**顺序承重**——Plan 02 的 5.4 定的是「多条覆盖同一目标由**列表顺序**决定、后者胜」，**不要按 `applied_at` 重排序**），"
     "并返回覆盖后的 `TrainingPackage` 投影。"
     "**⚠️ 调 `apply_overrides` 必须传 `exercises=`**（实测签名 `apply_overrides(pkg, records, *, exercises)`，"
     "关键字必填）—— 否则 `SUBSTITUTE_EXERCISE` 会留下旧动作的视频 URL，那是 Plan 02 顶回 2 逐字说的"
     "「一个看起来正常的谎」",
     1, "P4-A3/A4 教师覆盖的请求模型"),

    # 前后端对接的三条（P4-A5/A6/A7）
    ("- **`as_of` 由查询参数传，缺省取服务端当天**。",
     "- **⚠️ P4-A5（前后端对接缺口 1）：把两个身份头注册成 OpenAPI 的 `apiKey` securityScheme。** "
     "实测今天的 `openapi()[\"components\"]` 里**没有 `securitySchemes`**、spec 顶层**没有 `security`**、"
     "47 个路径里**声明过的 header 参数为空** —— 而 `X-Student-Id` / `X-Teacher-Staff-No` 是全部学生侧端点的必需头。"
     "**不注册的后果：Swagger UI 上没有地方能填它们、生成的 TS 客户端也不知道要发**，前端一接就撞 401 且不知道为什么。"
     "**⚠️ 用户 2026-10-08 明确要求「要确保后端和前端能够对接的上」，这一条是它的落点。**\n"
     "- **⚠️ P4-A6（前后端对接缺口 3）：给 `build_crud_router` 加 `pk_alias: str | None = None`。** "
     "实测 **23 个 detail 路径的 path 参数名 distinct = `['pk_value']`**（`/api/semesters/{pk_value}`），"
     "而签名里只有 `pk: str = 'id'`（DB 列名）、**没有给 OpenAPI 路径参数另起名的口子**。"
     "`None` → 自动取**资源路径的单数 + 下划线**（`semesters` → `semester_id`、`course-sections` → `course_section_id`、"
     "`fitness-test-results` → `fitness_test_result_id`），显式传则覆盖。**理由：生成的 TS 客户端里到处是 `pkValue` "
     "而不是 `semesterId`**；而这个改名是**纯 OpenAPI 层的**，不动 DB、不动路由匹配。"
     "**⚠️ 改完 23 个 detail 路径的 URL 模板会变，Task 3 那条遍历型守卫测试要跟着改。**\n"
     "- **⚠️ P4-A7（前后端对接缺口 2，本 Task 不修、只记录）**：CORS 是 `allow_origins=[\"*\"]` 且**没有 "
     "`allow_credentials`**（浏览器规范禁止两者并存）。**故 Plan 04 的前端不得用 cookie / "
     "`fetch(..., {credentials:'include'})`，身份只能走请求头。** 已写进本计划的「计划边界说明」。\n"
     "- **`as_of` 由查询参数传，缺省取服务端当天**。",
     1, "P4-A5/A6/A7 前后端对接三条"),

    # 计划边界说明：把 Plan 04 的约束写进去
    ("- **Plan 04 的**：Vue3 学生端 H5 与教师大屏、spec §9 的全部页面、`frontend/` 目录（今天不存在）。"
     "本计划交付**全部 HTTP 端点**，Plan 04 只写前端。",
     "- **Plan 04 的**：Vue3 学生端 H5 与教师大屏、spec §9 的全部页面、`frontend/` 目录（今天不存在）。"
     "本计划交付**全部 HTTP 端点**，Plan 04 只写前端。\n"
     "  **⚠️ Plan 04 必须遵守的三条对接约束（P4-A5/A6/A7 的产出，按硬规矩 #86 传导）**："
     "① **身份只能走请求头 `X-Student-Id` / `X-Teacher-Staff-No`，不得用 cookie 或 "
     "`fetch(..., {credentials:'include'})`** —— CORS 是 `allow_origins=[\"*\"]`，"
     "而浏览器规范禁止它与 `allow_credentials=True` 并存；"
     "② **两个身份头已注册成 OpenAPI 的 `apiKey` securityScheme**，故可以直接用 `/openapi.json` 生成 TS 客户端"
     "（`openapi-typescript` 之类），Swagger UI 上也有 Authorize 按钮；"
     "③ **23 个 detail 路径的参数名是资源单数 + `_id`**（`semester_id` / `course_section_id` / …），不是 `pk_value`。",
     1, "P4-A7 传导给 Plan 04"),
])

# ============ 账本 ============
lb = LEDGER.read_bytes()
lt = lb.decode("utf-8")
lnl = "\r\n" if "\r\n" in lt else "\n"
print(f"[ledger before] bytes={len(lb)} lines={lt.count(lnl)}")

BODY = """

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
"""

if lnl != "\n":
    BODY = BODY.replace("\r\n", "\n").replace("\n", lnl)
SENT = "Ruling 10 — 预检查出 1 Critical / 4 Important / 1 Minor"
assert SENT not in lt, f"{SENT!r} 已存在"
LEDGER.write_bytes((lt.rstrip("\r\n") + BODY).encode("utf-8"))
c2 = LEDGER.read_bytes().decode("utf-8")
print(f"[ledger after]  bytes={len(c2.encode('utf-8'))} lines={c2.count(lnl)}")
for k in ("Ruling 10", "硬规矩 #104", "控制者错误 #13", "P4-A1", "mappingproxy", "securitySchemes"):
    print(f"  {k}: {c2.count(k)}")
print(f"\n[edits] {len(edits)} 处：")
for lab, n in edits:
    print(f"  {n}x  {lab}")
