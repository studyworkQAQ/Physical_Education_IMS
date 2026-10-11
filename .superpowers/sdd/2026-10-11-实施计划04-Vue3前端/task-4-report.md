# Plan 04 Task 4 实现报告 —— 通用 CRUD 管理台（一个通用组件 + 一份 23 行资源目录）

> **日期**：2026-10-11 · **分支**：`feature/plan-04-frontend` · **起点 HEAD**：`5ad4d11`
> **交付**：`src/views/admin/{ResourceIndex,ResourceList,ResourceDetail}.vue`、
> `src/styles/admin.css`、`src/api/contract.ts`、`endpoints.ts` 的泛型 CRUD 五函数、
> `present.ts` 第 ⑨ 节、`catalog/resources.ts` 的一个可选字段、路由接线、删占位页
> **commit**：`022e7b8`（三个页面 + 路由 + 样式）、`5dad926`（API 层 + 标签）

---

## 1. 环境与演示库核实

| 项 | 实测 |
|---|---|
| Node / npm | v24.19.0 / 11.17.0 |
| FastAPI / SQLAlchemy | 0.141.1 / 2.1.3 |
| 开工时 HEAD / 工作树 | `5ad4d11` / 干净；分支 `feature/plan-04-frontend`（未切、未 push） |
| 开工时端口 | 8000 与 5173 **都还起着**（Task 3 留的 uvicorn 与 vite）；8000 那个在重灌演示库前已停掉 |
| `backend/pe.db` / `backend/data/seed/` | `False` / 0 文件（开工、中途、收尾各核一次） |
| 演示库 7 张表（重灌后） | students 60 · notifications 19 · prescriptions 60 · training_log 840 · rpe_record 240 · weekly_class_report 5 · alert 30（红 11 = RED_MINITEST_DROP 5 + RED_RPE_SUSTAINED 6；绿 13；黄 6；全 pending） |
| `exercises` / `prescription-templates` | **0 行 / 0 行**（重灌后仍是 0）；YAML 侧 24 个动作键 + 18 个模板文件都在 |

⚠️ 开工第一件事照硬规矩 #73 跑了版本三件套，与派单逐字一致。

## 2. `catalog/resources.ts` 的 23 行与后端实测的对拍

对拍口径（运行时，不用正则数源码）：`from app.api.routers.catalog import RESOURCES`
现读 `writable` / `on_delete` / `pk_alias`；`pkField` 再与 `/openapi.json` 里成员路径的
`parameters[in=path].name` 逐字对；`listExclude` 与 `crud._json_text_columns(model)`
现算的 `kept` 对（194 个槽位 / 122 个不同列名）。

**六个数全部与派单逐字相符，0 处不符**：资源 **23** / 可写 **9** / 只读 **14** /
`restrict` **12** / `forbid` **10** / `cascade` **1**（cascade 的那一个是 `class-sessions`）。
另实测：**有 DELETE 端点的只有 8 个**（9 个可写里 `semesters` 是 forbid）。

| # | resource | writable | onDelete | pkField（openapi 逐字同） | displayFields 列数 | listExclude（生效的） |
|---|---|---|---|---|---|---|
| 1 | semesters | true | forbid | semester_id | 5 | — |
| 2 | teachers | true | restrict | teacher_id | 2 ⚠️ | — |
| 3 | students | true | restrict | student_id | 5 | — |
| 4 | course-sections | true | restrict | course_section_id | 5 | — |
| 5 | enrollments | true | restrict | enrollment_id | 3 ⚠️ | — |
| 6 | fitness-test-batches | true | restrict | fitness_test_batch_id | 5 | — |
| 7 | fitness-test-results | false | forbid | fitness_test_result_id | 6 | — |
| 8 | body-compositions | true | restrict | body_composition_id | 6 | — |
| 9 | interest-surveys | true | restrict | interest_survey_id | 4 | dimensions, raw_answers |
| 10 | percentile-snapshots | false | forbid | percentile_snapshot_id | 6 | — |
| 11 | derived-metrics | false | forbid | derived_metric_id | 6 | annual_change, weaknesses, body_comp_reasons |
| 12 | stratification-results | false | forbid | stratification_result_id | 6 | input_snapshot |
| 13 | exercises | false | forbid | exercise_id | 4 | targets |
| 14 | prescription-templates | false | forbid | prescription_template_id | 6 | — |
| 15 | prescriptions | false | restrict | prescription_id | 6 | training_package, assembly_snapshot, safety_substitutions, teacher_overrides, trigger_reasons |
| 16 | weekly-adjustments | false | restrict | weekly_adjustment_id | 5 | — |
| 17 | class-sessions | true | cascade | class_session_id | 4 | rpe_token（**显式声明**；而它已不在 `ClassSessionRead` 上，故 list 类型无 `Omit`） |
| 18 | rpe-records | false | restrict | rpe_record_id | 4 | — |
| 19 | training-logs | false | restrict | training_log_id | 6 | — |
| 20 | mini-tests | false | restrict | mini_test_id | 6 | item_combo |
| 21 | alerts | false | forbid | alert_id | 6 | trigger_snapshot |
| 22 | notifications | false | forbid | notification_id | 5 | — |
| 23 | weekly-class-reports | false | forbid | weekly_class_report_id | 5 | layer_distribution, rpe_summary, checkin_rate_by_layer, progress_board, alert_summary |

⚠️ 两处「给不出 4–6 个」：`teachers` 的 list 类型只有 3 列、`enrollments` 只有 4 列
（其中一列是 `id`），故只能给 2 / 3 个。派单那句「挑 4–6 个」对这两行不可满足，
已在目录里逐行注释。

**结论**：目录的 23 行在 Task 1 就已写全且与后端逐字一致，本波**没有改任何一行的
既有字段**；只加了一个可选字段 `emptyNote`（`exercises` 与 `prescription-templates`
两行非空，理由见第 3 节）。

## 3. 三个页面的要点，与「只读资源按钮不出现」的实现方式

**实现方式是 `v-if`，不是路由级、也不是 `:disabled`。** 三个门，每门一个 `v-if`，
全文件**没有一处 `:disabled` 用在写按钮上**（分页按钮的 disabled 是另一回事）：

1. `!entry.writable`（14 个只读）→ 新建 / 编辑 / 删除**都不渲染**；页面上把目录的
   `readOnlyReason` 原样摊开（理由只有一个住址，页面不抄第二份）。
2. `!entry.hasDeleteEndpoint`（`on_delete='forbid'` 的 10 个，含可写的 `semesters`）
   → 删除不渲染，并写明「**不是权限不够，是这个操作不存在**」（打过去是 405
   `http_405`）；`semesters` 那一档单独写明它是全库的时间轴锚点、正确做法是把
   `is_current` 置 false。
3. `!identity.canWriteAsTeacher`（匿名或学生身份）→ 写按钮不渲染，并就地说明
   「9 个可写资源的 POST/PATCH/DELETE 全挂 `require_teacher`，匿名写是 401」，
   给出 `?teacher=T0001` 深链接。

**无头浏览器取证**（`--dump-dom` + 断言「按钮的标签原文与危险按钮的 class 都不在 DOM 里」）：
`exercises` / `prescription-templates` / `prescriptions` / `alerts` / `fitness-test-results`
五个只读资源的列表页与详情页都**不含** `＋ 新建一行` / `✎ 编辑` / `a-btn--danger`；
`semesters` 的教师身份列表页**含**新建、**不含** `a-btn--danger`；匿名身份下
`semesters` 也不含任何写按钮。全绿（`pe_t4_domassert.py`，TOTAL FAILS 0）。

**三个页面各自的要点**：

- **ResourceIndex**：23 格目录，顺序 = 目录 = 后端 `RESOURCES` = spec §4.1→§4.7。
  只读的 14 格用**砖红竖线 + 纸底色**在滚动之前就能扫出来；页面上 23/9/14/12/10/1/8
  七个数一律 `RESOURCES.filter(...)` 现算，一个都不写死。spec §4.4 逐字点名的
  `exercises` / `prescription-templates` 单独成一块。
- **ResourceList**：分页读**服务端生效**的信封四键（`limit`/`offset` 不读自己发出去的
  那一份）；每页 20/50/200 三档（后端 `deps.Page` 的上界就是 200）；新建表单**契约驱动**
  （见下）；行内删除一律二次确认，`cascade` 那一档逐字写明会连带删掉这节课的全部
  `rpe_record`；`restrict` 删除失败时把后端 `message`（点名了子表的那一句）**原样**显示
  在就地错误条里，上面一行是 `code` + 状态码 + `client.ts` 的处置建议。
  ⚠️ 刻意**不提供筛选框**：泛型 list 只有 `limit`/`offset`，`?rule_id=red` 会被 FastAPI
  静默忽略；一个「筛了但后端没筛」的界面比没有筛选更坏。
- **ResourceDetail**：read-one 的全部列逐格渲染；被 list 排掉的 19 个 `JsonText` 列打
  「列表里没有」的标记（于是「为什么列表页看不到它」在页面上有答案）；编辑表单
  **只送差集**，并在表单上方实时显示「将提交的差集（N 格）」；`class-sessions` 额外
  说明本页看不到 `rpe_token`（它已从 `ClassSessionRead` 上摘掉）。

**契约驱动的表单（`src/api/contract.ts`，派单 Create 清单里没有它）**：表单画哪几格读
`/openapi.json` 的 `components.schemas[*Create | *Update].properties`，于是「请求模型不收的
列不出现在表单里」自动成立。实测 9 个可写资源：`*Update` 的字段集与 `*Create` **逐字相等**、
`required` **全是 `[]`**、`*Read` = `*Create` + `id`。`JsonText` 列（`interest-surveys` 的
`dimensions` / `raw_answers`）渲染成跨满整行的 JSON 文本域 + `JSON.parse` 校验 ——
这是 23 个资源里**唯一需要 bespoke 控件**的一档；枚举列（`sex` / `grouping_mode` /
`timepoint`）**没有**做成下拉：它们的值域读不到契约（闸门是 `field_validator`），
硬抄一份就是第二个所有者，故一律文本框 + 后端 422 原样回显（422 的 `message` 会点名合法值）。

⚠️ 踩到并修掉的一格：POST 挂在**集合**路径、PATCH 挂在**成员**路径
（`/api/x/{pk_field}`）。拿集合路径查 PATCH 会**静默**得到 0 格而提交按钮照旧渲染
（看起来像「表单坏了」）。已加 `writePathOf()` 与「0 格就地报错、不画空表单」两道守卫。

⚠️ 为取证加的两个深链接：`?new=1` 落地打开新建表单、`?edit=1` 落地打开编辑表单
（理由同 `stores/identity.ts` 的 `adoptFromUrl`：一条链接落地时没有人去点按钮，
而 `--dump-dom` 不能交互）。两者都只在写按钮可见时生效，绕不过上面那三个门。
⚠️ 又因为 Vue 把输入框的值设在 **property** 上（序列化 HTML 里读不到），表单把
「将提交的请求体 / 差集」渲染成**文本** —— 编辑表单刚打开时差集必须是 `{}`，
这就证明了预填逐字等于 read-one 的原值（`pe_t4_formassert.py` 的
`edit_form:empty_diff_preview` / `edit_form:diff_count_zero`，全绿）。

## 4. 9 个可写资源逐个的新建 / 编辑 / 删除实测（真 HTTP，教师头 T0001）

| 资源 | POST | PATCH | DELETE |
|---|---|---|---|
| semesters | 201 | 200（weeks 18→19） | **405** `http_405`（forbid，端点不注册） |
| teachers | 201 | 200（改名） | 204 |
| students | 201 | 200（改院系） | 204 |
| course-sections | 201 | 200（改 schedule_text） | 204 |
| enrollments | 201 | 200（同值 PATCH：三列全是外键，没有自由文本列） | 204 |
| fitness-test-batches | 201 | 200（改 source） | 204 |
| body-compositions | 201 | 200（改 device） | 204 |
| interest-surveys | 201（含两个 JSON 列） | 200（total_score +0.5） | 204 |
| class-sessions | 201（撞自然键 `(section,date,period)` 是 409，换 period 即 201） | 200（period 11→12） | 204 |

配套实测：匿名 `POST /api/semesters` → **401 `unauthenticated`**（fix 波 1 的写入侧强制）；
只读资源 `POST /api/prescriptions`（匿名与教师头都是）→ **405 `http_405`**；
`DELETE /api/teachers/999999` → **404 `not_found`**。

**`restrict` 删除失败的人话错误原文**（管理台的就地错误条把 `message` 原样显示）：

```
DELETE /api/students/1  →  409
{"error":{"code":"integrity_conflict","message":"无法删除 student 1：alert.student_id 有 1 行；
body_composition.student_id 有 4 行；cleaning_log.student_id 有 3 行；derived_metrics.student_id 有 2 行；
enrollment.student_id 有 2 行；fitness_test_result.student_id 有 4 行；interest_survey.student_id 有 2 行；
mini_test.student_id 有 3 行；prescription.student_id 有 1 行；rpe_record.student_id 有 4 行；
stratification_result.student_id 有 2 行；training_log.student_id 有 15 行 仍指向它。
请先处理那些行，或改用重放。","detail":null}}
```

同型另两条：`course_section 1`（class_session 4 行 / enrollment 30 行 / weekly_class_report 1 行）、
`fitness_test_batch 1`（fitness_test_result 60 行）。⚠️ 「被谁引用」在 `message` 里、
`detail` 恒为 `null` —— 故横幅/错误条必须显示 `message` 原文，只显示 `integrity_conflict`
等于把信息丢掉。

**`cascade` 实测**（全库唯一一处）：建一节课 → `open-rpe` → 学生 4 交一条快评 →
删课前 `rpe_record` 里这节课 **1** 行 → `DELETE /api/class-sessions/9` → 204 →
删后 **0** 行。管理台在这一档的二次确认块里逐字写明了这一点。

## 5. 待清扫 / 关切 / 没按派单做的 / 顶回

**顶回（4 处）**：

1. **派单让 `present.ts`「加 23 个资源的中文标题」—— 没加，因为它已有住址**：
   `catalog/resources.ts` 的 `titleZh` 在 Task 1 就写全了 23/23。再抄一份的失效形态是
   「目录页显示『课堂课次』、列表页显示『课次』」而两处各自都对。改为在 `present.ts`
   加它**真正缺**的那一格：**141 个列名的中文标签**（122 = 23 个 list 项列名的并集，
   实测 194 槽位 / 122 不同名；+19 = 8 个资源被 list 排掉的 `JsonText` 列）+
   `cellText`（null → 「—」不是 0；boolean → 是/否；对象 → 一行压缩 JSON）+ `onDeleteZh`。
   认不出的列名**原样返回**而不是空串。
2. **`_SERVER_FILLED_COLUMNS` 的口径比派单窄**：实测它只有一条
   `{"/api/class-sessions": ("rpe_token",)}`（住址是 `tests/api/test_crud.py:1510`，
   `app/api/crud.py` 里没有这个名字）。派单举的 `submitted_at` / `late` 属于
   `training-logs` / `rpe-records` —— 那两个**不是泛型 CRUD 可写的**，管理台里根本没有表单；
   而 `batch_id` **在** `ClassSessionCreate` / `ClassSessionUpdate` 上（可空、缺省 null），
   故它**会**出现在表单里。判据一律是契约，不是一份清单。
3. **`catalog/resources.ts`「照它的形状补完」—— 它已经 100% 完整**（Task 1 交付，23/23 与
   后端逐字一致）。本波只加了一个可选字段 `emptyNote`。
4. **第 12 步第 ⑤ 拍（「每个 list 端点的响应确实未定型」）—— 确认成立，无顶回**：
   23/23 全是 `{type:object, additionalProperties:true}`，加 `/api/health` 共 24 个。

**没按派单做的（4 处）**：

1. 上面顶回 1（present.ts 的内容换了）。
2. 派单 Create 清单外新增了 `src/api/contract.ts` 与 `vite.config.ts` 的
   `server.proxy['/openapi.json']`（它不在 `/api` 前缀下，不加则开发期打到 vite 自己身上）。
3. 管理台加了 `?new=1` / `?edit=1` 两个深链接与「将提交的请求体 / 差集」文本预览
   （为取证，也为可用性）。
4. 截图用 ASCII 文件名：PowerShell 5.1 读无 BOM 的 UTF-8 `.ps1` 会把中文文件名写坏
   （第一版截图落地成了乱码名）。

**待清扫（5 条）**：

1. `base.css:286` 的 `#a93623`（Task 2 已登记）仍是全仓唯一写在 `tokens.css` 之外的色值；
   本波**没有增加第二个**（`admin.css` 零字面色值）。
2. `client.ts:285-286` 与 `App.vue` 的注释仍写「47 个 GET 全部匿名」—— Task 3 已顶回为
   48 匿名 / 58 GET，注释没同步。
3. `interest-surveys` 的两个 JSON 文本域只有 `JSON.parse` 层面的校验，形状错了要等后端 422。
4. 管理台刻意不提供筛选；大表（`training_log` 840 行）只能翻页。要筛得客户端拉全量或后端开窄端点。
5. 第 10 步（Task 5 的 smoke）建的学期留在演示库里（forbid 删不掉）；重跑 `demo.ps1` 即清。

**关切（2 条）**：

1. `/openapi.json` 278 KB，每会话拉一次（模块级缓存那个 Promise）。生产部署若不给它
   加缓存头，每次硬刷新都会重拉。
2. 无头浏览器取证依赖 Edge 的常见安装路径（可用 `PE_BROWSER` 覆盖）；找不到时第 14 步
   **红**而不是静默跳过。

## 6. 最终验收

- `npm run build` **退出码 0**：119 modules；产物 20 个文件（13 个 JS chunk + 7 个 CSS），
  主 chunk CSS **65.50 kB**（gzip 10.46）/ JS **148.05 kB**（gzip 52.61）；
  共享 chunk `present-*.js` 70.69 kB、`contract-*.js` 2.33 kB、`resources-*.js` 10.81 kB；
  管理台三个懒加载 chunk：ResourceIndex 5.06 / ResourceList 16.87 / ResourceDetail 12.35 kB。
- 全仓 `@ts-ignore` / `@ts-expect-error` / `as any`：**0 处**（唯一一次类型断言是
  `ResourceList` 里把 23 个 list 项类型的并集收成 `Record<string, unknown>` 的那一个函数，
  已注释理由）。
- 23 个资源全部能在管理台读到列表与详情；9 个可写资源能新建/编辑/删除（第 4 节）；
  14 个只读资源看不到任何写按钮（第 3 节的无头取证）；删除被引用的资源能看到人话错误
  （第 4 节原文）；`exercises` 与 `prescription-templates` 的空列表有解释（目录的 `emptyNote`，
  列表页空态原样显示）。
- 无头浏览器 21 个 URL 的 DOM 断言（14 个页面态 + 7 个表单态）**全绿**
  （`pe_t4_domassert.py` 与 `pe_t4_formassert.py`，各 TOTAL FAILS 0）。
- 后端 1260 passed / 覆盖率四格 / 端点 65/93：**逐字不变**（见 task-5-report 第 5 节）。
- commit：`022e7b8`、`5dad926`（本报告与取证文档、截图在下一个 commit 入库）。
