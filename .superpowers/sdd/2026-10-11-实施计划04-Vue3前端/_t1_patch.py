"""Plan 04 计划更正 v2（Task 1 顶回的 2 条 Critical + 3 条 Important）+ commit。
⚠️ v1 的第 4 处锚点写错了（计划的 File Structure 是树形，不是列表），断言当场挡住、文件未改。
"""
import pathlib
import subprocess

P = pathlib.Path(r"c:\Users\whwenhao\Desktop\Physical_Education_ims\Document\2026-10-11-实施计划04-Vue3前端.md")
raw = P.read_bytes()
t = raw.decode("utf-8")
nl = "\r\n" if "\r\n" in t else "\n"
print(f"[before] {len(raw)} B / {t.count(nl)} 行  nl={'CRLF' if nl != chr(10) else 'LF'}")
edits = []

PAIRS = [
    ("5. **⚠️ 92 个操作里有 24 个的响应 schema 是 `{\"type\":\"object\",\"additionalProperties\":true}`** —— 即 **23 个泛型 list 端点 + `/api/health`**。**codegen 生成出来是 `Record<string, unknown>`**。这是后端 `crud.py:544-555` 逐字交代过的取舍（挂 `response_model` 会让 `defer` 掉的大 JSON 列触发 N+1）。**处置：前端手写这 23 个 `Omit<XRead, …JsonText列>` 类型**（终审说的另一条路是给后端工厂加窄化的 `*ListRead`，**本计划不改后端**，因为那会动 Task 3 的核心工厂）。⚠️ **list 项的键集合 = 该资源 `schemas.read` 的字段 减去 `list_exclude`** —— 这个差集**今天只有 `class-sessions` 一个资源非空**（`list_exclude=(\"rpe_token\",)`，fix 波 2 加的）。",
     "5. **⚠️ 92 个操作里有 24 个的响应 schema 是 `{\"type\":\"object\",\"additionalProperties\":true}`** —— 即 **23 个泛型 list 端点 + `/api/health`**（Task 1 实测坐实：产物里 `[key: string]: unknown;` 出现 **42** 次 = 24 次在 `operations` 内 + 18 次在 `components` 内 + 0 次在 `paths` 内）。**codegen 生成出来是 `Record<string, unknown>`**。这是后端 `crud.py:544-555` 逐字交代过的取舍（挂 `response_model` 会让 `defer` 掉的大 JSON 列触发 N+1）。**处置：前端手写这 23 个 list 类型**（终审说的另一条路是给后端工厂加窄化的 `*ListRead`，**本计划不改后端**，因为那会动 Task 3 的核心工厂）。\n"
     "   **⚠️⚠️ Task 1 顶回 1（Critical）：本条原来那句「list 项的键集合 = `schemas.read` 减去 `list_exclude`，且这个差集今天只有 `class-sessions` 一个非空」是说反的。** 后端 `crud.py:582-585` 逐字是 `excluded = list_exclude if list_exclude is not None else _json_text_columns(model)` —— **`list_exclude` 是「覆盖」自动探测，不是「追加」**。故**真实口径是**：\n"
     "   - **list 项的键集合 = `*Read` 的字段集 减去「该资源生效的排除集」**，而**生效的排除集 = 显式 `list_exclude`（若有）否则 = 该模型的全部 `JsonText` 列**。\n"
     "   - **实测相对 `*Read` 少列的是 8 个资源 / 19 列**：`interest-surveys`(2) `derived-metrics`(3) `stratification-results`(1) `exercises`(1) `prescriptions`(5) `mini-tests`(1) `alerts`(1) `weekly-class-reports`(5)。\n"
     "   - ⚠️ **而 `class-sessions` 是唯一显式声明 `list_exclude=(\"rpe_token\",)` 的资源，它恰恰是唯一差集为空的**（6 == 6，因为 `rpe_token` 早已不在 `ClassSessionRead` 上，fix 波 2 摘掉的）—— **与原句正好相反**。\n"
     "   - **照原句写的后果**：8 个 list 类型会声明 API 根本不返回的字段 → 运行时 `undefined` → **管理台列表一片空白，且静默**。（Task 1 已按真口径写完并逐个核过：**23/23 对称差为空**。）\n"
     "   - **⚠️ 已实测的 23 个字段数**（Task 1 报告 §6，**Task 4 的管理台照它写**）：`6/3/7/6/4/6/21/8/5/14/8/9/6/10/11/8/6/6/11/9/13/10/7`。",
     1, "顶回1 约束5 说反了"),

    ("17. **三个动作值**：`POST /api/alerts/{alert_id}/handle` 的 `action` ∈ `ACTION_REDUCE` / `ACTION_IGNORE` / `ACTION_NOTE`（常量住在 `app/api/routers/alerts.py`）。⚠️ **前端要从 `/openapi.json` 读枚举，不要抄字符串。**",
     "17. **三个动作值**：`POST /api/alerts/{alert_id}/handle` 的 `action` ∈ `ACTION_REDUCE` / `ACTION_IGNORE` / `ACTION_NOTE`（常量住在 `app/api/routers/alerts.py`）。\n"
     "   **⚠️ Task 1 顶回 4：原句「前端要从 `/openapi.json` 读枚举」做不到** —— `AlertHandleCreate.action` 在 schema 里逐字是 `{\"type\":\"string\",\"title\":\"Action\"}`，**闸门是 `field_validator`，而 validator 不进 JSON Schema**；**全库唯一的 enum schema 是 `OverrideKind`**。\n"
     "   **处置（Task 1 已落地）**：三档**字面写出**，并在 **Task 5 的联调脚本里加一条对拍守卫**（逐个 `POST` 一个非法 `action` 断言 422；再断言三档合法值都被接受）—— **这是「枚举不在契约里」时唯一能做的机器守卫**。",
     1, "顶回4 约束17 做不到"),

    ("8. **错误体是统一形状**：`{\"error\": {\"code\": str, \"message\": str, \"detail\": Any | null}}`。**前端要按 `code` 分支，不要按 `message` 字符串匹配**（`message` 是给人看的中文，会变）。已知 code 清单：`unauthenticated` / `unknown_teacher` / `unknown_student` / `forbidden` / `not_found` / `invalid_rpe_token` / `rpe_not_opened` / `rpe_already_submitted` / `no_active_prescription` / `alert_not_pending` / `conflict`。⚠️ **这份清单要由实现者从后端源码实测补全**（`Grep` `code=` 在 `app/api/` 下的全部命中），不要照抄本行。",
     "8. **错误体是统一形状**：`{\"error\": {\"code\": str, \"message\": str, \"detail\": Any | null}}`。**前端要按 `code` 分支，不要按 `message` 字符串匹配**（`message` 是给人看的中文，会变）。\n"
     "   **⚠️ Task 1 已用 AST 实测出完整清单（14 个具名 + 一个通配）**，本行原来那份 11 个的清单**有 4 个不存在、漏了 8 个**：\n"
     "   - **14 个具名**：`unauthenticated`(401) `forbidden`(403) `not_found`(404) `integrity_conflict`(409) `unprocessable_value`(422) `request_validation_failed`(422) `internal_error`(500) `alert_not_pending`(409) `not_recipient`(403) `no_weekly_report`(404) `rpe_not_opened`(409) `invalid_rpe_token`(403) `no_active_prescription`(404) `outside_microcycle`(404)\n"
     "   - **通配**：`http_<状态码>`（今天最常见的是 **`http_405`** —— 只读资源被写时就是它）\n"
     "   - ⚠️ **原清单里 4 个不存在**：`unknown_teacher` / `unknown_student`（**不在册是 403 `forbidden`**）、`rpe_already_submitted`（**重复交快评撞唯一约束 → 409 `integrity_conflict`**）、`conflict`（**逐字是 `integrity_conflict`**）。\n"
     "   - ⚠️ **Task 1 顶回 3：原句给的取证方法抓不到它们** —— `Grep 'code='` 在 `backend/app` 命中 16 处**全是 `status_code=`**；15 个 `error_response(…)` 的 `code` 一律是**位置实参**。**必须用 AST。**",
     1, "顶回3 错误code清单"),

    ("| 类型 | **`openapi-typescript` 生成 + 23 个手写 list 类型** | 见 Global Constraints 第 5 条 |",
     "| 类型 | **`openapi-typescript` **7.13.0** 生成 + 23 个手写 list 类型** | 见 Global Constraints 第 5 条。**⚠️ Task 1 顶回 2（Critical）：v7 的取值路径与本计划原先设想的不同** —— v7 的 `paths` 里每个 method **只有一行** `get: operations[\"list_rows_api_students_get\"]`，**响应体内联在 `operations` 侧**。故 Task 2–4 一律照这四条取值：模型 `components['schemas']['StudentRead']`；响应体 `operations['<operationId>']['responses'][200]['content']['application/json']`；参数 `operations[op]['parameters']['query' \\| 'header']`；**`operationId` 是 FastAPI 自动生成的**（`list_rows_api_x_get` / `read_one_api_x__pk__get` / `create_row_api_x_post`）。⚠️ **`endpoints.ts` 刻意只走 `components['schemas']` + 手写 list 类型、不依赖 `paths` 的形状**，故 v7→v8 的升级代价被隔离在 0。产物 **338 756 B / 7 971 行**，重跑 SHA256 逐字不变 |",
     1, "顶回2 codegen取值路径"),

    ("**演示库实测**：2 学期 / 60 学生 / 5 教学班 / 120 选课 / 60 处方 / 8 课次 / 240 快评 / 840 打卡 / 180 小测 / **11 条预警** / **19 条通知**（电子勋章 13 + 补练提醒 6）/ **5 份班级周报**（三层完成率 0.5–0.79）。",
     "**演示库实测**（`demo.ps1` 跑完的口径）：2 学期 / 60 学生 / **3 教师**（`T0001` 陈国华、`T0002` 林慧敏、`T0003` 赵志刚）/ 5 教学班 / 120 选课 / 60 处方 / 8 课次 / 240 快评 / 840 打卡 / 180 小测 / **11 条预警** / **19 条通知**（电子勋章 13 + 补练提醒 6）/ **5 份班级周报**（三层完成率 0.5–0.79）。\n"
     "   **⚠️ Task 1 的待清扫第 1 条：仓库里现存的那个 `pe_demo.db` 与上面这份清单不符** —— 它的 `notifications` 只有 **1** 条（且那 1 条是人工处置预警的痕迹：`is_read=true`、`created_at=2026-10-10T16:43:12`），`exercises` 与 `prescription-templates` 是**空表**；其余 10 项逐字吻合。**它是 fix 波 1 改 `demo_bootstrap` 之前灌的旧库。→ Task 2/3/5 开工前一律先重跑 `demo.ps1`。**",
     1, "待清扫1 旧演示库"),

    ("9. **分页是 `limit` / `offset` 查询参数，响应是 `{\"items\": [...], \"total\": int}`**",
     "9. **分页是 `limit` / `offset` 查询参数，响应是 `{\"items\": [...], \"limit\": int, \"offset\": int, \"total\": int}`（⚠️ Task 1 半顶回：**是 4 个键不是 2 个**）**",
     1, "分页信封4个键"),
]

for old, new, count, label in PAIRS:
    if nl != "\n":
        old = old.replace("\r\n", "\n").replace("\n", nl)
        new = new.replace("\r\n", "\n").replace("\n", nl)
    n = t.count(old)
    assert n == count, f"[{label}] 期望 {count}，实为 {n}\n  old={old[:100]!r}"
    t = t.replace(old, new)
    edits.append(label)

P.write_bytes(t.encode("utf-8"))
c = P.read_bytes().decode("utf-8")
print(f"[after]  {len(c.encode('utf-8'))} B / {c.count(nl)} 行")
print(f"[edits] {len(edits)} 处：")
for e in edits:
    print(f"  OK {e}")
for k in ("Task 1 顶回 1", "Task 1 顶回 2", "Task 1 顶回 3", "Task 1 顶回 4", "integrity_conflict", "7.13.0", "8 个资源 / 19 列"):
    print(f"  {k}: {c.count(k)}")

ROOT = P.parents[1]
subprocess.run(["git", "add", "Document/2026-10-11-实施计划04-Vue3前端.md",
                ".superpowers/sdd/2026-10-11-实施计划04-Vue3前端/"], cwd=str(ROOT), check=True)
r = subprocess.run(["git", "commit", "-m",
                    "docs: Plan04 计划更正 —— Task 1 顶回 5 处（2 Critical：约束5 的 list 键集合口径说反了、codegen v7 的取值路径不同）"
                    "+ 错误 code 清单实测 14 个（原 11 个里 4 个不存在、漏 8 个）+ 约束17 的枚举读不到 + 旧演示库与清单不符；Task 1 报告入库"],
                   cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
out = (r.stdout or r.stderr).strip().splitlines()
print("  " + (out[1] if len(out) > 1 else out[0] if out else "(无输出)"))
r = subprocess.run(["git", "log", "--oneline", "-3"], cwd=str(ROOT), capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
print((r.stdout or "").strip())
r = subprocess.run(["git", "status", "--short"], cwd=str(ROOT), capture_output=True,
                   text=True, encoding="utf-8", errors="replace")
print(f"git status -> {(r.stdout or '').strip() or '（干净）'}")
