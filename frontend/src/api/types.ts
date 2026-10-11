/**
 * `types.ts` —— **23 个手写的 list 类型** + 分页信封 + 少数几个后端也没定型的响应。
 *
 * ---------------------------------------------------------------------------
 * 为什么要有这个文件（计划约束第 5 条）
 * ---------------------------------------------------------------------------
 * 后端 92 个操作里有 **24 个**的响应 schema 是 `{"type": "object",
 * "additionalProperties": true}` —— 即 **23 个泛型 list 端点 + `/api/health`**。
 * `openapi-typescript` 把它们生成成 `{ [key: string]: unknown }`
 * （等价于 `Record<string, unknown>`），于是 `res.items[0].name` 一次都不类型安全。
 *
 * 这是后端 `app/api/crud.py:631-644` 逐字交代过的取舍：list 端点**不挂**
 * `response_model`，改为「显式只 SELECT `kept` 那些列、手工拼 dict」——
 * 一个含全部列的 `response_model` 会让 FastAPI 在序列化阶段 `getattr` 每个字段，
 * 被 `defer` 掉的 `JsonText` 列于是触发 N+1，「排除大 JSON 列」的收益当场归零。
 * 代价就是 OpenAPI 里没有形状，**由本文件补**。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 那 24 个未定型响应的实测清单（`openapi-typescript` 产物里逐个复核过）
 * ---------------------------------------------------------------------------
 * 数法：`app.openapi()`（**不是** `len(app.routes)` —— FastAPI 0.141.1 的
 * `include_router` 是惰性的，`app.routes` 只数得出 **6** 个，按它写的守卫是假绿的）
 * 遍历 64 个 `/api/` 路径模板的 92 个操作，挑出「某个 2xx 响应的 schema 是
 * `{"type":"object","additionalProperties":true}` 且不含 `$ref`/`oneOf`/`anyOf`/
 * `allOf`/`items`」的。命中 **24** 个，与计划逐字一致：
 *
 *      1  GET /api/alerts                      13  GET /api/percentile-snapshots
 *      2  GET /api/body-compositions           14  GET /api/prescription-templates
 *      3  GET /api/class-sessions              15  GET /api/prescriptions
 *      4  GET /api/course-sections             16  GET /api/rpe-records
 *      5  GET /api/derived-metrics             17  GET /api/semesters
 *      6  GET /api/enrollments                 18  GET /api/stratification-results
 *      7  GET /api/exercises                   19  GET /api/students
 *      8  GET /api/fitness-test-batches        20  GET /api/teachers
 *      9  GET /api/fitness-test-results        21  GET /api/training-logs
 *     10  GET /api/interest-surveys            22  GET /api/weekly-adjustments
 *     11  GET /api/mini-tests                  23  GET /api/weekly-class-reports
 *     12  GET /api/notifications               24  GET /api/health
 *
 * 产物里它们逐个长成这样（以 `list_rows_api_alerts_get` 为例，
 * `src/api/generated/schema.d.ts:7764-7775`）：
 *
 *     responses: { 200: { content: { "application/json": { [key: string]: unknown } } } }
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ list 项的键集合到底等于什么（对计划约束第 5 条的一处更正）
 * ---------------------------------------------------------------------------
 * 计划说的是「`*Read` 的字段集 **减去 `list_exclude`**」，并说「这个差集今天只有
 * `class-sessions` 一个资源非空」。**这只对「显式声明的 `list_exclude`」成立。**
 * 后端 `crud.py:582-585` 的实际算式是：
 *
 *     excluded = list_exclude if list_exclude is not None else _json_text_columns(model)
 *     kept     = [c.name for c in table.columns if c.name not in excluded]
 *
 * 即：**没有显式声明 `list_exclude` 的资源，排掉的是自动探测出来的全部 `JsonText` 列**
 * （判据是 `isinstance(column.type, JsonText)`，见 `crud.py:237-259`）。实测有 **9** 个
 * 资源的 list 响应因此少了列，其中 8 个是自动探测、1 个是显式声明：
 *
 *     class-sessions         rpe_token（**显式声明**，Plan 03 收尾小修波加的）
 *     interest-surveys       dimensions, raw_answers
 *     derived-metrics        annual_change, weaknesses, body_comp_reasons
 *     stratification-results input_snapshot
 *     exercises              targets
 *     prescriptions          training_package, assembly_snapshot, safety_substitutions,
 *                            teacher_overrides, trigger_reasons
 *     mini-tests             item_combo
 *     alerts                 trigger_snapshot
 *     weekly-class-reports   layer_distribution, rpe_summary, checkin_rate_by_layer,
 *                            progress_board, alert_summary
 *
 * 于是本文件的口径是「`*Read` 的字段集 减去 **生效的** excluded」，并逐个实测过
 * 它与后端 `kept` **集合相等**（23/23 的对称差全为空 —— 取证见 task-1-report.md 第 4 节）。
 * 能这样写的理由是：23 个资源里只有 `class-sessions` 的 `*Read` 字段集 ≠ 表列集
 * （差一个 `rpe_token`，fix 波 2 从读模型上摘掉的），其余 22 个逐字相等。
 *
 * ⚠️ 要拿到那些被排掉的列，请调 **read-one**（`GET /api/<资源>/{id}`，
 * 它挂 `response_model=schemas.read`、含全部 `JsonText` 列）。
 */
import type { components } from './generated/schema'

/** `components['schemas']` 的简写。⚠️ 它是**生成的**，不要在这里加东西。 */
type S = components['schemas']

/**
 * `Omit` 的严格版：`K` 必须是 `T` 的键。
 *
 * ⚠️ 原生 `Omit<T, K>` 对「`K` 不在 `T` 上」**静默通过**（它的定义是
 * `Pick<T, Exclude<keyof T, K>>`）。而本文件那 23 行的全部价值就在于
 * 「排掉的键确实是 Read 模型上的键」—— 后端哪天把一个 `JsonText` 列从
 * Read 模型上摘掉（正如 fix 波 2 对 `rpe_token` 做的那样），原生 `Omit`
 * 会照样编译通过、而这一行会静默变成一个**谎**（声称有一个 list 端点
 * 根本不返回的字段）。用 `K extends keyof T` 之后，那一档是 `npm run build` 的红。
 */
type OmitStrict<T, K extends keyof T> = Omit<T, K>

/* ==========================================================================
   分页信封
   ========================================================================== */

/**
 * 泛型 list 端点的响应信封。
 *
 * ⚠️ **4 个键，不是 2 个**（计划约束第 9 条写的是 `{"items": [...], "total": int}`，
 * 少写了后两个）。实测 `GET /api/students?limit=200` 的响应键集合逐字是
 * `items,limit,offset,total`（`app/api/crud.py:653-658` 的 `return` 字面量）。
 * `limit` / `offset` 是**服务端生效的那一份**（`deps.Page` 有缺省值
 * `limit=50` / `offset=0`，且 `1 <= limit <= 200`、`offset >= 0`），
 * 故前端算「下一页的 offset」要读它，不要读自己发出去的那一份。
 */
export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

/** `deps.Page` 的查询参数（`limit` 上界 **200**、下界 **1**；`offset` 下界 **0**）。
 *
 *  ⚠️⚠️ **是 `type` 不是 `interface`，这不是风格问题**：`client.ts` 的
 *  `ApiRequestInit.query` 是 `Record<string, QueryValue>`，而 TypeScript
 *  **只给「对象字面量类型」隐式索引签名，不给 `interface`**
 *  （interface 是**开放的**，declaration merging 可以随时给它加成员，
 *  故编译器不敢假设它只有已声明的那几个键）。写成 `interface PageQuery` 会让
 *  23 个 list 函数逐个报
 *  `Index signature for type 'string' is missing in type 'PageQuery'`。
 *  Task 2–4 再定义查询袋类型时同理：**一律用 `type`**。 */
export type PageQuery = {
  limit?: number
  offset?: number
}

/* ==========================================================================
   24 个未定型响应里的第 24 个：/api/health
   ========================================================================== */

/**
 * `GET /api/health`。**24 个未定型响应里唯一不是 list 的那一个。**
 * 字段集实测自活的响应原文：`{"status": "ok", "tables": 25, "students": 60}`
 * （后端 `app/api/routers/health.py` 的返回字面量；它的 docstring 逐字写着这个形状）。
 */
export interface HealthRead {
  status: string
  tables: number
  students: number
}

/* ==========================================================================
   23 个 list 项类型
   ==========================================================================
   ⚠️ 顺序与后端 `app/api/routers/catalog.py` 的 `RESOURCES` 那 23 行**逐行同序**
      （= spec §4.1 → §4.7 的顺序），故三处可以逐行对拍。
   ⚠️ 每一行的注释里写了「生效的 excluded」与「排掉的字段数」。
   ========================================================================== */

/* ---- spec §4.1 组织与身份（5 个）---- */

/** `/api/semesters` · `SemesterRead` 的 **6** 个字段 · 无排除。 */
export type SemesterListItem = S['SemesterRead']

/** `/api/teachers` · `TeacherRead` 的 **3** 个字段 · 无排除。 */
export type TeacherListItem = S['TeacherRead']

/** `/api/students` · `StudentRead` 的 **7** 个字段 · 无排除。 */
export type StudentListItem = S['StudentRead']

/** `/api/course-sections` · `CourseSectionRead` 的 **6** 个字段 · 无排除。 */
export type CourseSectionListItem = S['CourseSectionRead']

/** `/api/enrollments` · `EnrollmentRead` 的 **4** 个字段 · 无排除。 */
export type EnrollmentListItem = S['EnrollmentRead']

/* ---- spec §4.2 学期节点数据（4 个）---- */

/** `/api/fitness-test-batches` · `FitnessTestBatchRead` 的 **6** 个字段 · 无排除。 */
export type FitnessTestBatchListItem = S['FitnessTestBatchRead']

/** `/api/fitness-test-results` · `FitnessTestResultRead` 的 **21** 个字段 · 无排除。
 *  ⚠️ 23 个资源里字段最多的一个，且**一个 `JsonText` 列都没有**（21 列全是标量）。 */
export type FitnessTestResultListItem = S['FitnessTestResultRead']

/** `/api/body-compositions` · `BodyCompositionRead` 的 **8** 个字段 · 无排除。 */
export type BodyCompositionListItem = S['BodyCompositionRead']

/** `/api/interest-surveys` · `InterestSurveyRead` 的 7 个字段 **减 2** = **5**。
 *  排掉（自动探测的 `JsonText` 列）：`dimensions`、`raw_answers`。 */
export type InterestSurveyListItem = OmitStrict<
  S['InterestSurveyRead'],
  'dimensions' | 'raw_answers'
>

/* ---- spec §4.3 派生与分层（3 个）---- */

/** `/api/percentile-snapshots` · `PercentileSnapshotRead` 的 **14** 个字段 · 无排除。 */
export type PercentileSnapshotListItem = S['PercentileSnapshotRead']

/** `/api/derived-metrics` · `DerivedMetricsRead` 的 11 个字段 **减 3** = **8**。
 *  排掉：`annual_change`、`weaknesses`、`body_comp_reasons`。
 *  ⚠️ 于是「这个学生的短板是哪几项」在 list 里拿不到，只有 `weakness_count` 那个数；
 *  要清单请调 read-one。 */
export type DerivedMetricsListItem = OmitStrict<
  S['DerivedMetricsRead'],
  'annual_change' | 'weaknesses' | 'body_comp_reasons'
>

/** `/api/stratification-results` · `StratificationResultRead` 的 10 个字段 **减 1** = **9**。
 *  排掉：`input_snapshot`。
 *  ⚠️ `label`（红/黄/绿）**在** list 里，故大屏的分层分布可以直接读 list；
 *  而「这个 label 是由哪几个输入算出来的」只有 read-one 才有。 */
export type StratificationResultListItem = OmitStrict<
  S['StratificationResultRead'],
  'input_snapshot'
>

/* ---- spec §4.4 处方（4 个）---- */

/** `/api/exercises` · `ExerciseRead` 的 7 个字段 **减 1** = **6**。
 *  排掉：`targets`。 */
export type ExerciseListItem = OmitStrict<S['ExerciseRead'], 'targets'>

/** `/api/prescription-templates` · `PrescriptionTemplateRead` 的 **10** 个字段 · 无排除。
 *  ⚠️ 本资源**刻意只读**（spec §4.4：18 套模板 YAML 是唯一所有者，本表是
 *  `sync_templates` 的投影），故没有 Create/Update 类型可用。 */
export type PrescriptionTemplateListItem = S['PrescriptionTemplateRead']

/** `/api/prescriptions` · `PrescriptionRead` 的 16 个字段 **减 5** = **11**。
 *  排掉：`training_package`、`assembly_snapshot`、`safety_substitutions`、
 *  `teacher_overrides`、`trigger_reasons`。
 *  ⚠️ 这是 23 个里排得最狠的一个（5 个 `JsonText` 列全排）。故「训练单长什么样」
 *  一律走 `GET /api/students/{id}/weekly-sheet`（它是特例端点、有自己的 schema），
 *  **不要**指望从 list 里读 `training_package`。 */
export type PrescriptionListItem = OmitStrict<
  S['PrescriptionRead'],
  | 'training_package'
  | 'assembly_snapshot'
  | 'safety_substitutions'
  | 'teacher_overrides'
  | 'trigger_reasons'
>

/** `/api/weekly-adjustments` · `WeeklyAdjustmentRead` 的 **8** 个字段 · 无排除。
 *  ⚠️ 计划约束第 13 条：`source='auto'` + `factor=0.8` 是红色预警触发的那一档，
 *  而**一处方一周至多一条 auto 调整** —— 故同一周命中两条红色规则时，
 *  这里只有一行，而 `alert` 表有两行。 */
export type WeeklyAdjustmentListItem = S['WeeklyAdjustmentRead']

/* ---- spec §4.5 反馈三源（4 个）---- */

/** `/api/class-sessions` · `ClassSessionRead` 的 **6** 个字段 · **无 `Omit`**。
 *
 *  ⚠️⚠️ 23 行里**唯一**显式声明了 `list_exclude` 的资源（`("rpe_token",)`），
 *  但它也是**唯一**一个「`*Read` 字段集 ≠ 表列集」的资源：`rpe_token` 在
 *  Plan 03 收尾小修波里已经**从 `ClassSessionRead` 上摘掉了**，故这里无键可排 ——
 *  写 `OmitStrict<…, 'rpe_token'>` 会当场编译报错（`rpe_token` 不是
 *  `ClassSessionRead` 的键），而那正是 `OmitStrict` 存在的理由。
 *
 *  那一波修的是**两半**（`catalog.py:414-429` 逐字交代）：摘读模型只堵住了
 *  read-one / POST / PATCH 三个端点，而泛型 list **不走** `response_model`，
 *  故还得在目录里显式排一次。实测匿名 `GET /api/class-sessions` 的响应键集合是
 *  `batch_id,course_section_id,id,period,rpe_opened,session_date` —— **不含口令** ✓。
 *
 *  ⚠️ 教师要显示口令只能调 `GET /api/class-sessions/{id}/rpe-token`（教师头）；
 *  学生端一律**手输**（计划约束第 15 条）。 */
export type ClassSessionListItem = S['ClassSessionRead']

/** `/api/rpe-records` · `RpeRecordRead` 的 **6** 个字段 · 无排除。
 *  ⚠️ 本资源 `writable=False`，写入**只走** `POST /api/rpe-records`（特例端点，
 *  学生头）：要校验口令，且 `submitted_at` 必须服务端填。 */
export type RpeRecordListItem = S['RpeRecordRead']

/** `/api/training-logs` · `TrainingLogRead` 的 **11** 个字段 · 无排除。
 *  ⚠️ 同上：`submitted_at` 与 `late` 都由服务端算，前端**不要传**
 *  （计划 Task 2 的「每日打卡」那一行）。 */
export type TrainingLogListItem = S['TrainingLogRead']

/** `/api/mini-tests` · `MiniTestRead` 的 10 个字段 **减 1** = **9**。
 *  排掉：`item_combo`。
 *  ⚠️ `normalized_score` **在** list 里，且它可能是 `null`（样本不足）——
 *  计划约束第 10 条：显示「—」，不要显示 0。 */
export type MiniTestListItem = OmitStrict<S['MiniTestRead'], 'item_combo'>

/* ---- spec §4.6 预警与通知（2 个）---- */

/** `/api/alerts` · `AlertRead` 的 14 个字段 **减 1** = **13**。
 *  排掉：`trigger_snapshot`。
 *  ⚠️ `student_id` 与 `course_section_id` **恰好一个非空**（DB 侧
 *  `ck_alert_subject_is_exactly_one` 强制）→ 前端按哪一列非空分支渲染
 *  （学生卡片 vs 班级卡片）。⚠️ 而 `subject_key` 是它们的归一化形态，
 *  那个前缀算式的所有者是后端 `app/domain/alerts.py`，**前端不要自己拼、也不要解析它**。
 *  ⚠️ 预警去重靠 DB（`(rule_id, subject_key, semester_id, window_key)` 唯一），
 *  故**前端不需要自己去重**（计划约束第 18 条）。 */
export type AlertListItem = OmitStrict<S['AlertRead'], 'trigger_snapshot'>

/** `/api/notifications` · `NotificationRead` 的 **10** 个字段 · 无排除。
 *  ⚠️ 收件人是**多态的**（`recipient_kind` + `recipient_id` 两列，
 *  `recipient_id` 不是外键）→ 本类型**同时**服务两个端点：
 *   - `GET /api/notifications`（匿名，读到的是**全部收件人**的行，管理台用）；
 *   - `GET /api/students/{id}/notifications`（**学生头**，服务端已按收件人过滤，
 *     学生端的消息中心用）。⚠️ 后者是 Plan 04 Task 3 的后端小修波加的
 *     —— Task 2 实测的结论「**不存在**这个端点」在那一波之后**已过期**。
 *     它回的是**裸数组**（不是 `Page`），且**已在服务端按 `created_at` 降序排好**。
 *  ⚠️ 两者的**项**形状逐字相同（同一个 `NotificationRead`），故一个类型够用；
 *  守卫是后端 `tests/api/test_dashboard.py` 的
 *  `test_the_notification_list_returns_only_the_requesters_rows_newest_first`
 *  （它从 `/openapi.json` 实读那 10 列、与响应体逐行对账）。 */
export type NotificationListItem = S['NotificationRead']

/* ---- spec §4.7 班级周报（1 个）---- */

/** `/api/weekly-class-reports` · `WeeklyClassReportRead` 的 12 个字段 **减 5** = **7**。
 *  排掉：`layer_distribution`、`rpe_summary`、`checkin_rate_by_layer`、
 *  `progress_board`、`alert_summary`。
 *  ⚠️ 于是**教师大屏与班级周报一律走特例端点**
 *  `GET /api/dashboard/weekly-class-report/{course_section_id}`
 *  （它挂 `response_model=WeeklyClassReportRead`、含全部 5 个聚合列）。
 *  本 list 类型只有 `suggestion` 那一句人话 + 三个 id + 周次 + 生成时刻，
 *  适合做「哪几周有周报」的索引。 */
export type WeeklyClassReportListItem = OmitStrict<
  S['WeeklyClassReportRead'],
  | 'layer_distribution'
  | 'rpe_summary'
  | 'checkin_rate_by_layer'
  | 'progress_board'
  | 'alert_summary'
>

/* ==========================================================================
   资源名 → list 项类型 的映射
   ========================================================================== */

/**
 * 23 个资源的路径段 → 它的 list 项类型。
 *
 * ⚠️ **它是 `src/catalog/resources.ts` 那 23 行的类型侧对偶**：目录里的
 * `resource` 字段与本映射的键集合必须相等（Task 5 的守卫会两边对拍，
 * 于是「后端加第 24 个资源」会让 `npm run build` 红，而不是静默漏掉）。
 */
export interface ListItemByResource {
  semesters: SemesterListItem
  teachers: TeacherListItem
  students: StudentListItem
  'course-sections': CourseSectionListItem
  enrollments: EnrollmentListItem
  'fitness-test-batches': FitnessTestBatchListItem
  'fitness-test-results': FitnessTestResultListItem
  'body-compositions': BodyCompositionListItem
  'interest-surveys': InterestSurveyListItem
  'percentile-snapshots': PercentileSnapshotListItem
  'derived-metrics': DerivedMetricsListItem
  'stratification-results': StratificationResultListItem
  exercises: ExerciseListItem
  'prescription-templates': PrescriptionTemplateListItem
  prescriptions: PrescriptionListItem
  'weekly-adjustments': WeeklyAdjustmentListItem
  'class-sessions': ClassSessionListItem
  'rpe-records': RpeRecordListItem
  'training-logs': TrainingLogListItem
  'mini-tests': MiniTestListItem
  alerts: AlertListItem
  notifications: NotificationListItem
  'weekly-class-reports': WeeklyClassReportListItem
}

/** 23 个资源的路径段（与 `ListItemByResource` 的键同源，故不会漂）。 */
export type ResourceName = keyof ListItemByResource

/* ==========================================================================
   三个动作值（`POST /api/alerts/{alert_id}/handle` 的 `action`）
   ========================================================================== */

/**
 * ⚠️⚠️ **对计划约束第 17 条的一处更正**：计划说「前端要从 `/openapi.json`
 * 读枚举」。实测**读不到** —— `AlertHandleCreate.action` 在 OpenAPI 里逐字是
 * `{"type": "string", "title": "Action"}`，**没有 `enum`**：那三档的闸门是
 * `app/api/schemas/alerts.py:195-206` 的一个 `field_validator`（走 `one_of`），
 * 而 Pydantic 的 validator 不进 JSON Schema。
 * （对照：同一份 OpenAPI 里 `OverrideKind` **是**枚举 —— 它是 `str, Enum`，
 * 故生成出来是 `"weekly_frequency" | "substitute_exercise" | …`。两档不同源。）
 *
 * 故这里字面写出那三档，**唯一所有者**是后端
 * `app/api/schemas/alerts.py:79` 的 `HANDLE_ACTIONS: tuple[str, ...]`
 * （`app/api/routers/alerts.py:173-175` 的 `ACTION_REDUCE` / `ACTION_IGNORE` /
 * `ACTION_NOTE` import 它、不抄第二份）。⚠️ 值是**下划线**风格
 * （`reduce_20pct`），与 URL 的连字符惯例相反。
 * ⚠️ Task 5 的联调脚本要把这三档与后端的 `HANDLE_ACTIONS` 对拍一次。
 */
export const HANDLE_ACTIONS = {
  /** 减量 20%：写一条 `weekly_adjustment`（`source='auto'`、`factor=0.8`）+ 发一条站内消息。
   *  ⚠️ 两处副作用都**可能没有发生**（那一周已经有 auto 调整了），
   *  故响应里的 `adjustment` / `notification` 可能是 `null` —— 那是**有信息的一档**。 */
  reduce: 'reduce_20pct',
  /** 忽略：只改 `alert.status`。 */
  ignore: 'ignore',
  /** 备注：只写 `handled_action` 一列，`status` **保持 pending**。
   *  ⚠️ 这一档 `note` 必填且不得为空白，否则 **422 `unprocessable_value`**。 */
  note: 'note',
} as const

/** `HANDLE_ACTIONS` 的三个值。 */
export type HandleAction = (typeof HANDLE_ACTIONS)[keyof typeof HANDLE_ACTIONS]
