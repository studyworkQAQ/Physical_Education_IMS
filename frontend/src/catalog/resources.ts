/**
 * `catalog/resources.ts` —— **23 个资源的目录**（前端这一侧的唯一住址）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 它是后端 `backend/app/api/routers/catalog.py` 的 `RESOURCES` 的**第二个所有者**
 * ---------------------------------------------------------------------------
 * 后端用**一个泛型工厂**（`app/api/crud.py` 的 `build_crud_router`）生成了 23 个资源的
 * 路由，故前端也用**一个通用组件 + 一份 23 行的目录**，而不是 23 套页面
 * （计划 Task 4：手写 23 套会产生 23 份互相不一致的分页/错误/空态行为）。
 *
 * 代价就是「两个所有者」，故计划第 4 节要求一条守卫：**Task 5 的联调脚本要从
 * `/openapi.json` 反查**这 23 个资源是否都存在、且 `writable=false` 的那 **14** 个
 * 确实没有 POST/PATCH/DELETE —— 否则后端加第 24 个资源时前端会**静默漏掉**。
 *
 * ---------------------------------------------------------------------------
 * 每一行的字段从哪来（**运行时口径**，硬规矩 #89：不用正则数源码）
 * ---------------------------------------------------------------------------
 * `resource` / `writable` / `onDelete` / `pkField` / `listExclude*`
 *     由 `from app.api.routers.catalog import RESOURCES` 在 Python 里 `json.dumps`
 *     出来逐行抄的（**不是**读源码文本）。`pkField` 用的是
 *     `r.get("pk_alias") or _pk_alias_of(r["path"])` —— 即后端**真正**放进 URL 模板的
 *     那个名字，与 `/openapi.json` 里 detail 路径的 parameter name 逐字相同。
 * `listExclude`
 *     ⚠️ 是**生效的**那一组，不是「显式声明的」那一组。后端 `crud.py:582-585`：
 *     `excluded = list_exclude if list_exclude is not None else _json_text_columns(model)`。
 *     故 8 个资源虽然没声明 `list_exclude`，list 响应里仍然少了它们的 `JsonText` 列。
 *     显式声明的那一组（今天只有 `class-sessions`）单独放在 `listExcludeDeclared` 里。
 * `titleZh` / `displayFields` / `readOnlyReason`
 *     前端自己定的（给人看的中文标题、列表页显示哪几列、只读的理由）。
 *     ⚠️ `displayFields` 一律从**该资源的 list 项类型**里挑（不是从 `*Read` 挑），
 *     于是「挑了一个 list 端点根本不返回的列」在 `npm run build` 上就红
 *     —— 靠下面那个 {@link defineResource} 的泛型形参做到的。
 */
import type { ListItemByResource, ResourceName } from '../api/types'

/** `on_delete` 的三档。⚠️ 值与后端 `app/api/crud.py` 的
 *  `ON_DELETE_RESTRICT` / `ON_DELETE_FORBID` / `ON_DELETE_CASCADE` 逐字相同。 */
export type OnDelete = 'restrict' | 'forbid' | 'cascade'

/**
 * 「泛型已擦掉」的那一层。**字段的全部说明都住在这里**（单一所有者），
 * {@link ResourceEntry} 只负责把三个字段收窄。
 */
export interface ResourceEntryBase {
  /** 资源的路径段（复数 + 连字符），= `ListItemByResource` 的键。 */
  readonly resource: ResourceName
  /** 完整路径。⚠️ 与后端 `RESOURCES[i]["path"]` 逐字相同（工厂不再加前缀）。 */
  readonly path: string
  /** 中文标题（给人看的）。 */
  readonly titleZh: string
  /** **必须与后端 `RESOURCES` 的 `writable` 逐字一致。** 23 行里 **9** 个 `true`。 */
  readonly writable: boolean
  /** **必须与后端逐字一致。** 实测 `restrict` **12** / `forbid` **10** / `cascade` **1**。 */
  readonly onDelete: OnDelete
  /** DELETE 端点**存不存在**。⚠️ `writable && onDelete !== 'forbid'`：
   *  10 个 `forbid` 的资源根本不注册 DELETE（打过去是 **405**），
   *  而 `semesters` 是「可写 + forbid」的那一个，故 9 个可写资源里只有 **8** 个有 DELETE
   *  （这正是「26 个泛型 CRUD 写入操作」而不是 27 个的理由）。 */
  readonly hasDeleteEndpoint: boolean
  /** detail 路径的 pk 参数名。⚠️ 23 行里唯一的手工覆盖是
   *  `fitness-test-batches` → `fitness_test_batch_id`（自动推导对 `-es` 结尾的复数
   *  会多留一个 `e`）。 */
  readonly pkField: string
  /** 列表页显示哪几列。⚠️ **必须是 list 项类型的键**（`defineResource` 会验）。 */
  readonly displayFields: readonly string[]
  /** list 响应里**实际缺少**的列（= `*Read` 的字段减去它）。 */
  readonly listExclude: readonly string[]
  /** 后端**显式声明**的 `list_exclude`。⚠️ 今天只有 `class-sessions` 一行非空。 */
  readonly listExcludeDeclared: readonly string[]
  /** `writable=false` 的理由（管理台要把它显示出来，计划约束第 20 条）。
   *  `writable=true` 的资源一律 `null`。 */
  readonly readOnlyReason: string | null
}

/**
 * **逐行**的类型（`defineResource` 的形参类型）。它把 base 的三个字段收窄到具体的 `R`。
 *
 * ⚠️⚠️ **数组一律用 {@link ResourceEntryBase}，不要用本类型**：
 * `ResourceEntry`（缺省 `R = ResourceName`）的 `displayFields` 是
 * `readonly (keyof ListItemByResource[ResourceName] & string)[]`，而
 * `ListItemByResource[ResourceName]` 是 23 个 list 项类型的**并集**，
 * `keyof` 一个并集得到的是**交集** —— 实测塌成 `"id"`（23 个资源唯一共有的键），
 * 于是 `readonly ResourceEntry[]` 会让 22 行当场红：
 * `Type '"student_id"' is not assignable to type '"id"'`。
 * 一个数组必须是同质的，而 23 行的 `R` 各不相同，故数组这一层只能擦掉 `R`；
 * 逐行的类型安全由 {@link defineResource} 在**字面量那一处**保住（那一处 `R` 是具体的）。
 */
export interface ResourceEntry<R extends ResourceName = ResourceName> extends ResourceEntryBase {
  readonly resource: R
  readonly path: `/api/${R}`
  readonly displayFields: readonly (keyof ListItemByResource[R] & string)[]
}

/**
 * 只是把泛型形参钉住，让 `displayFields` 与 `resource` 互相校验。
 *
 * ⚠️ 它是**编译期**的：`npm run build` 会把「挑了一个 list 端点不返回的列」
 * 与「`resource` 拼错」都变成红。运行时它什么都不做（原样返回）。
 */
function defineResource<R extends ResourceName>(entry: ResourceEntry<R>): ResourceEntry<R> {
  return entry
}

/**
 * 23 行。**顺序与后端 `RESOURCES` 那 23 行逐行同序**（= spec §4.1 → §4.7），
 * 故三处可以逐行对拍。
 */
export const RESOURCES: readonly ResourceEntryBase[] = [
  // ---------------------------------------------------------------------
  // spec §4.1 组织与身份（5 个，全部可写）
  // ---------------------------------------------------------------------
  defineResource({
    resource: 'semesters',
    path: '/api/semesters',
    titleZh: '学期',
    writable: true,
    onDelete: 'forbid',
    hasDeleteEndpoint: false,
    pkField: 'semester_id',
    displayFields: ['name', 'start_date', 'end_date', 'weeks', 'is_current'],
    listExclude: [],
    listExcludeDeclared: [],
    readOnlyReason: null,
  }),
  defineResource({
    resource: 'teachers',
    path: '/api/teachers',
    titleZh: '教师',
    writable: true,
    onDelete: 'restrict',
    hasDeleteEndpoint: true,
    pkField: 'teacher_id',
    // ⚠️ 本资源只有 3 列，故这里给不出 4–6 个（计划 Task 4 那句「挑 4–6 个」
    //    对它是不可满足的）。
    displayFields: ['staff_no', 'name'],
    listExclude: [],
    listExcludeDeclared: [],
    readOnlyReason: null,
  }),
  defineResource({
    resource: 'students',
    path: '/api/students',
    titleZh: '学生',
    writable: true,
    onDelete: 'restrict',
    hasDeleteEndpoint: true,
    pkField: 'student_id',
    displayFields: ['student_no', 'name', 'sex', 'grade', 'department'],
    listExclude: [],
    listExcludeDeclared: [],
    readOnlyReason: null,
  }),
  defineResource({
    resource: 'course-sections',
    path: '/api/course-sections',
    titleZh: '教学班',
    writable: true,
    onDelete: 'restrict',
    hasDeleteEndpoint: true,
    pkField: 'course_section_id',
    displayFields: ['name', 'semester_id', 'teacher_id', 'grouping_mode', 'schedule_text'],
    listExclude: [],
    listExcludeDeclared: [],
    readOnlyReason: null,
  }),
  defineResource({
    resource: 'enrollments',
    path: '/api/enrollments',
    titleZh: '选课',
    writable: true,
    onDelete: 'restrict',
    hasDeleteEndpoint: true,
    pkField: 'enrollment_id',
    // ⚠️ 本资源只有 4 列（其中一列是 id），故只有 3 个可挑。
    displayFields: ['semester_id', 'student_id', 'course_section_id'],
    listExclude: [],
    listExcludeDeclared: [],
    readOnlyReason: null,
  }),
  // ---------------------------------------------------------------------
  // spec §4.2 学期节点数据（4 个：3 可写 + 1 只读）
  // ---------------------------------------------------------------------
  defineResource({
    resource: 'fitness-test-batches',
    path: '/api/fitness-test-batches',
    titleZh: '体测批次',
    writable: true,
    onDelete: 'restrict',
    hasDeleteEndpoint: true,
    // ⚠️ 23 行里唯一的手工覆盖（多一个 e 的那个自动推导）。
    pkField: 'fitness_test_batch_id',
    displayFields: ['timepoint', 'test_date', 'semester_id', 'source', 'academic_year'],
    listExclude: [],
    listExcludeDeclared: [],
    readOnlyReason: null,
  }),
  defineResource({
    resource: 'fitness-test-results',
    path: '/api/fitness-test-results',
    titleZh: '体测成绩',
    writable: false,
    onDelete: 'forbid',
    hasDeleteEndpoint: false,
    pkField: 'fitness_test_result_id',
    displayFields: ['student_id', 'tested_on', 'total_score', 'national_grade', 'height_cm', 'weight_kg'],
    listExclude: [],
    listExcludeDeclared: [],
    readOnlyReason:
      '乐跑投影 + 批处理输入：改它等于改原始数据，而下游的百分位快照、短板计数与趋势全部由它算出 —— 改一行会静默改变整批学生的分层。',
  }),
  defineResource({
    resource: 'body-compositions',
    path: '/api/body-compositions',
    titleZh: '体成分',
    writable: true,
    onDelete: 'restrict',
    hasDeleteEndpoint: true,
    pkField: 'body_composition_id',
    displayFields: ['student_id', 'measured_on', 'muscle_mass_kg', 'body_fat_pct', 'smi', 'device'],
    listExclude: [],
    listExcludeDeclared: [],
    readOnlyReason: null,
  }),
  defineResource({
    resource: 'interest-surveys',
    path: '/api/interest-surveys',
    titleZh: '兴趣问卷',
    writable: true,
    onDelete: 'restrict',
    hasDeleteEndpoint: true,
    pkField: 'interest_survey_id',
    displayFields: ['student_id', 'semester_id', 'filled_on', 'total_score'],
    listExclude: ['dimensions', 'raw_answers'],
    listExcludeDeclared: [],
    readOnlyReason: null,
  }),
  // ---------------------------------------------------------------------
  // spec §4.3 派生与分层（3 个，全部只读 + forbid）
  // ---------------------------------------------------------------------
  defineResource({
    resource: 'percentile-snapshots',
    path: '/api/percentile-snapshots',
    titleZh: '百分位快照',
    writable: false,
    onDelete: 'forbid',
    hasDeleteEndpoint: false,
    pkField: 'percentile_snapshot_id',
    displayFields: ['item', 'sex', 'age_group', 'p50', 'sample_size', 'computed_on'],
    listExclude: [],
    listExcludeDeclared: [],
    readOnlyReason: '批处理产物：删它的正确方式是重放（POST /api/pipeline/run-daily 按 batch_id 先删后算）。',
  }),
  defineResource({
    resource: 'derived-metrics',
    path: '/api/derived-metrics',
    titleZh: '派生指标',
    writable: false,
    onDelete: 'forbid',
    hasDeleteEndpoint: false,
    pkField: 'derived_metric_id',
    displayFields: ['student_id', 'computed_on', 'trend', 'weakness_count', 'valid_count', 'body_comp_abnormal'],
    listExclude: ['annual_change', 'weaknesses', 'body_comp_reasons'],
    listExcludeDeclared: [],
    readOnlyReason: '批处理产物：由 percentile_stage 算出，要改请重跑批处理。',
  }),
  defineResource({
    resource: 'stratification-results',
    path: '/api/stratification-results',
    titleZh: '分层结果',
    writable: false,
    onDelete: 'forbid',
    hasDeleteEndpoint: false,
    pkField: 'stratification_result_id',
    displayFields: ['student_id', 'computed_on', 'label', 'hit_rules', 'percentile_source', 'valid_from'],
    listExclude: ['input_snapshot'],
    listExcludeDeclared: [],
    readOnlyReason:
      '批处理产物，且它是 spec §4.3「可追溯性」的核心：改一行 label，那条行就无法再离线复算了。',
  }),
  // ---------------------------------------------------------------------
  // spec §4.4 处方（4 个，全部只读）
  // ---------------------------------------------------------------------
  defineResource({
    resource: 'exercises',
    path: '/api/exercises',
    titleZh: '动作库',
    writable: false,
    onDelete: 'forbid',
    hasDeleteEndpoint: false,
    pkField: 'exercise_id',
    displayFields: ['ref', 'name', 'impact_level', 'equipment'],
    listExclude: ['targets'],
    listExcludeDeclared: [],
    readOnlyReason:
      'spec §4.4 逐字：「这是体育专家维护的知识资产……改阈值应走版本控制与评审，不应在运行时改数据库」。backend/data/exercises.yaml 是唯一所有者，本表是 sync_exercises 的投影 —— 开放 API 写它会让那句话变成假的（下一次 sync 会把 API 的改动静默覆盖掉）。',
  }),
  defineResource({
    resource: 'prescription-templates',
    path: '/api/prescription-templates',
    titleZh: '处方模板',
    writable: false,
    onDelete: 'forbid',
    hasDeleteEndpoint: false,
    pkField: 'prescription_template_id',
    displayFields: ['template_ref', 'layer', 'weakness', 'body_comp', 'review_status', 'reachable'],
    listExclude: [],
    listExcludeDeclared: [],
    readOnlyReason:
      'spec §4.4 同上：18 套模板 YAML 是唯一所有者，本表是 sync_templates 的投影。',
  }),
  defineResource({
    resource: 'prescriptions',
    path: '/api/prescriptions',
    titleZh: '运动处方',
    writable: false,
    onDelete: 'restrict',
    hasDeleteEndpoint: false,
    pkField: 'prescription_id',
    displayFields: ['student_id', 'template_ref', 'label_at_generation', 'status', 'valid_from', 'generated_on'],
    listExclude: [
      'training_package',
      'assembly_snapshot',
      'safety_substitutions',
      'teacher_overrides',
      'trigger_reasons',
    ],
    listExcludeDeclared: [],
    readOnlyReason:
      '教师覆盖与状态变更走特例端点（POST …/overrides、POST …/regenerate）：直接 PATCH 整行会让 training_package 与 assembly_snapshot 失去一致性。',
  }),
  defineResource({
    resource: 'weekly-adjustments',
    path: '/api/weekly-adjustments',
    titleZh: '周训练量调整',
    writable: false,
    onDelete: 'restrict',
    hasDeleteEndpoint: false,
    pkField: 'weekly_adjustment_id',
    displayFields: ['prescription_id', 'week', 'factor', 'source', 'reason'],
    listExclude: [],
    listExcludeDeclared: [],
    readOnlyReason:
      "source='auto' 由管道的 alert_stage 写、'teacher' 由覆盖端点写；开放 CRUD 写它会绕过 WeeklyFactor 的 (0, 2] 校验 —— factor 在 DB 侧刻意不加 CHECK，故 API 是它唯一的闸门。",
  }),
  // ---------------------------------------------------------------------
  // spec §4.5 反馈三源（4 个：1 可写 + 3 只读）
  // ---------------------------------------------------------------------
  defineResource({
    resource: 'class-sessions',
    path: '/api/class-sessions',
    titleZh: '课堂课次',
    writable: true,
    // ⚠️ 全库唯一的 cascade：教师取消课次，则这节课的 rpe_record 一并作废。
    onDelete: 'cascade',
    hasDeleteEndpoint: true,
    pkField: 'class_session_id',
    displayFields: ['course_section_id', 'session_date', 'period', 'rpe_opened'],
    listExclude: ['rpe_token'],
    // ⚠️ 23 行里唯一显式声明 list_exclude 的一行（Plan 03 收尾小修波）。
    //    它是「rpe_token 不再匿名可读」的另一半：泛型 list 不走 response_model，
    //    故只从 ClassSessionRead 上摘掉那一列堵不住 list。
    //    ⚠️ 而 rpe_token 今天**已经不在** ClassSessionRead 上了，
    //    故 api/types.ts 的 ClassSessionListItem 没有 Omit（写了会编译报错）。
    listExcludeDeclared: ['rpe_token'],
    readOnlyReason: null,
  }),
  defineResource({
    resource: 'rpe-records',
    path: '/api/rpe-records',
    titleZh: '课堂快评',
    writable: false,
    onDelete: 'restrict',
    hasDeleteEndpoint: false,
    pkField: 'rpe_record_id',
    displayFields: ['class_session_id', 'student_id', 'rpe', 'submitted_at'],
    listExclude: [],
    listExcludeDeclared: [],
    readOnlyReason:
      '写入只走 POST /api/rpe-records（学生头）：要校验教师投屏的口令，且 submitted_at 必须服务端填（学生端的时钟不可信，而它是 RED_RPE_SUSTAINED「连续三次」那个判据的输入）。',
  }),
  defineResource({
    resource: 'training-logs',
    path: '/api/training-logs',
    titleZh: '每日打卡',
    writable: false,
    onDelete: 'restrict',
    hasDeleteEndpoint: false,
    pkField: 'training_log_id',
    displayFields: ['student_id', 'log_date', 'completed', 'duration_min', 'late', 'source'],
    listExclude: [],
    listExcludeDeclared: [],
    readOnlyReason:
      '写入只走 POST /api/training-logs（学生头）：late 必须服务端算（spec §8.1 的 00:00–22:00 窗口；完成率是 RCT 的关键过程指标，必须严格）。',
  }),
  defineResource({
    resource: 'mini-tests',
    path: '/api/mini-tests',
    titleZh: '二次小测',
    writable: false,
    onDelete: 'restrict',
    hasDeleteEndpoint: false,
    pkField: 'mini_test_id',
    displayFields: ['student_id', 'semester_id', 'week', 'squat_30s_count', 'shuttle_20m_s', 'normalized_score'],
    listExclude: ['item_combo'],
    listExcludeDeclared: [],
    readOnlyReason:
      '写入只走 POST /api/mini-tests/batch（教师头）：normalized_score 要班内百分位反查，客户端算不出来。',
  }),
  // ---------------------------------------------------------------------
  // spec §4.6 预警与通知（2 个，只读 + forbid）
  // ---------------------------------------------------------------------
  defineResource({
    resource: 'alerts',
    path: '/api/alerts',
    titleZh: '预警',
    writable: false,
    onDelete: 'forbid',
    hasDeleteEndpoint: false,
    pkField: 'alert_id',
    displayFields: ['rule_id', 'level', 'status', 'student_id', 'course_section_id', 'triggered_at'],
    listExclude: ['trigger_snapshot'],
    listExcludeDeclared: [],
    readOnlyReason:
      'alert 是「哪个学生在哪一天被哪条规则标记过」的审计记录（RCT 的过程数据），且它今天没有子行 —— 故用 forbid 而不是 restrict（restrict 在这里等价于「随便删」，那会静默抹掉研究数据）。由 alert_stage 生成、由 POST /api/alerts/{id}/handle 处置；开放 CRUD 写它会绕过 window_key 去重。',
  }),
  defineResource({
    resource: 'notifications',
    path: '/api/notifications',
    titleZh: '站内消息',
    writable: false,
    onDelete: 'forbid',
    hasDeleteEndpoint: false,
    pkField: 'notification_id',
    displayFields: ['title', 'recipient_kind', 'channel', 'is_read', 'created_at'],
    listExclude: [],
    listExcludeDeclared: [],
    readOnlyReason:
      '它是学生看到的消息历史，且刻意不带 batch_id（用户实时写入），故也不在重放的清单里 —— 即「从任何入口都删不掉一行通知」，这是有意的。「已读」走 POST /api/notifications/{id}/read（改 is_read，不删行）。',
  }),
  // ---------------------------------------------------------------------
  // spec §4.7 班级周报（1 个，只读 + forbid）
  // ---------------------------------------------------------------------
  defineResource({
    resource: 'weekly-class-reports',
    path: '/api/weekly-class-reports',
    titleZh: '班级周报',
    writable: false,
    onDelete: 'forbid',
    hasDeleteEndpoint: false,
    pkField: 'weekly_class_report_id',
    displayFields: ['course_section_id', 'semester_id', 'week', 'suggestion', 'generated_at'],
    listExclude: [
      'layer_distribution',
      'rpe_summary',
      'checkin_rate_by_layer',
      'progress_board',
      'alert_summary',
    ],
    listExcludeDeclared: [],
    readOnlyReason:
      '批处理产物（report_stage，只在周日生成）。5 个 JsonText 聚合列的形状由那个生成器定，从 API 改一行会让「环比流动」的基准与库里其余各行矛盾。',
  }),
]

/** 按资源名查一行。⚠️ 返回 `undefined` 而不是抛错：调用方（管理台的路由）
 *  拿到 `undefined` 时要显示「不认识的资源」，而抛错会让整个视图白屏。 */
export function resourceByName(resource: string): ResourceEntryBase | undefined {
  return RESOURCES.find((entry) => entry.resource === resource)
}
