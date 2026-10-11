/**
 * `endpoints.ts` —— **每个端点一个函数**。
 *
 * ---------------------------------------------------------------------------
 * 为什么不做通用工厂（计划第 4 节逐字）
 * ---------------------------------------------------------------------------
 * 92 个操作里只有 **23 个是同形的**（那 23 个泛型 list），其余 69 个各有各的
 * 参数、身份头与响应形状。一个「传资源名就能调」的工厂换来的是：
 * 函数签名不再有类型、IDE 补不出参数名、而 4 个真实存在的差异
 * （`semesters` 没有 DELETE、`fitness-test-batches` 的 pk 别名多一个 `e`、
 * `mini-tests/batch` 是 200 不是 201、`rpe-records` 与 `training-logs` 的 POST
 * 不是 CRUD 的 POST）要在工厂里开四个特例口子。故这里一个端点一个函数。
 *
 * ---------------------------------------------------------------------------
 * 三个约定
 * ---------------------------------------------------------------------------
 * 1. **身份头不在这里传**：由 `client.ts` 从 `stores/identity` 注入。
 *    每个函数的注释里写了它**要**哪个头，于是「这个调用会不会 401」在读代码时就能回答。
 *    ⚠️ 计划约束第 3 条那句「47 个 GET 全部匿名」**措辞是错的**（Plan 04 Task 2 顶回
 *    的第 3 处）：GET 里**有一部分挂 `security`**（学生侧与教师侧的窄读端点），
 *    只有其余的是匿名的。**写请求一律要教师头**。
 *    ⚠️⚠️ **本处刻意不写「各有多少个」**（Plan 04 收尾波改的）：那个数在 Plan 04 的
 *    5 个 Task + 收尾波里变了 **4** 次（47 → 57 → 58 → 本波 59），写死就一定会再过期一次
 *    ——凡是能从别处读出来的数，一律视为过期（Plan 03 硬规矩 #111）。
 *    **机器口径的两个住址**（要数就去看它们，不要相信任何注释里的数字）：
 *      · `scripts/smoke.mjs` **第 12 步**：从 `/openapi.json` **反查**
 *        `catalog/resources.ts` 的 23 行，其中一拍就是「哪些 (路径, 方法) 带 security」；
 *      · `backend/tests/api/test_prescription_api.py` 的
 *        `test_the_identity_headers_are_registered_as_openapi_security_schemes`：
 *        它持有一份**字面**的「带身份的特例端点」清单（收尾波之后 20 项）
 *        + 全仓合计断言，并且它的 docstring 逐字写着「每加一个带身份的特例端点
 *        都要回来加一行——这是**有意的**」。
 *    ⚠️ 想知道「某一个端点要哪个头」，看**它自己那一格的注释**（下面每个函数都有），
 *    那一格与端点定义住在一起、不会与合计数字一起过期。
 * 2. **路径参数一律用后端的 pk 别名**（`semesterId` / `fitnessTestBatchId` / …）。
 *    ⚠️ 计划约束第 7 条：23 个 detail 路径的参数名是「资源单数 + `_id`」，
 *    **不是** `pk_value`（Plan 03 Task 4 专门改过，就是为了 codegen 出可读的签名）。
 *    ⚠️ 唯一的手工覆盖是 `fitness-test-batches` → `fitness_test_batch_id`
 *    （自动推导对 `-es` 结尾的复数会多留一个 `e`，后端 `crud.py:_pk_alias_of`
 *    的 docstring 逐字交代了「推导保持笨而可预测，笨错的那一个显式覆盖」）。
 * 3. **`204` 的端点返回 `Promise<void>`**（`client.ts` 不解析 body）。
 *    ⚠️ 8 个 DELETE 全是 204。
 */
import { apiRequest } from './client'
import type { components } from './generated/schema'
import type {
  AlertListItem,
  BodyCompositionListItem,
  ClassSessionListItem,
  CourseSectionListItem,
  DerivedMetricsListItem,
  EnrollmentListItem,
  ExerciseListItem,
  FitnessTestBatchListItem,
  FitnessTestResultListItem,
  HandleAction,
  HealthRead,
  InterestSurveyListItem,
  ListItemByResource,
  MiniTestListItem,
  NotificationListItem,
  Page,
  PageQuery,
  PercentileSnapshotListItem,
  PrescriptionListItem,
  PrescriptionTemplateListItem,
  ResourceName,
  RpeRecordListItem,
  SemesterListItem,
  StratificationResultListItem,
  StudentListItem,
  TeacherListItem,
  TrainingLogListItem,
  WeeklyAdjustmentListItem,
  WeeklyClassReportListItem,
} from './types'

/** `components['schemas']` 的简写。⚠️ 生成的，不要在这里加东西。 */
type S = components['schemas']

/* ==========================================================================
   存活探针
   ========================================================================== */

/** `GET /api/health` · 匿名 · ⚠️ 24 个未定型响应之一，形状由 `types.ts` 手补。 */
export function getHealth(): Promise<HealthRead> {
  return apiRequest<HealthRead>('GET', '/api/health')
}

/* ==========================================================================
   spec §4.1 组织与身份（5 个资源，全部可写）
   ========================================================================== */

/** `GET /api/semesters` · 匿名。 */
export function listSemesters(query?: PageQuery): Promise<Page<SemesterListItem>> {
  return apiRequest('GET', '/api/semesters', { query })
}

/** `POST /api/semesters` · **教师头** · 201。⚠️ 撞 `semester.name` → 409 `integrity_conflict`。 */
export function createSemester(body: S['SemesterCreate']): Promise<S['SemesterRead']> {
  return apiRequest('POST', '/api/semesters', { body })
}

/** `GET /api/semesters/{semester_id}` · 匿名。 */
export function readSemester(semesterId: number): Promise<S['SemesterRead']> {
  return apiRequest('GET', `/api/semesters/${semesterId}`)
}

/** `PATCH /api/semesters/{semester_id}` · **教师头**。 */
export function updateSemester(
  semesterId: number,
  body: S['SemesterUpdate'],
): Promise<S['SemesterRead']> {
  return apiRequest('PATCH', `/api/semesters/${semesterId}`, { body })
}

// ⚠️ **没有 deleteSemester**：`semesters` 是 23 行里唯一 `on_delete='forbid'`
//    而**又**可写的资源，故后端根本不注册 DELETE 端点（打过去是 405 `http_405`）。
//    全库的时间轴锚点：9 张表按 `semester_id` 归组，「这个学期不要了」的正确做法是
//    把 `is_current` 置 false。这也是「26 个泛型 CRUD 写入操作」而不是 27 个的理由。

/** `GET /api/teachers` · 匿名。⚠️ 身份切换器读它拉教师名单。 */
export function listTeachers(query?: PageQuery): Promise<Page<TeacherListItem>> {
  return apiRequest('GET', '/api/teachers', { query })
}

/** `POST /api/teachers` · **教师头** · 201。 */
export function createTeacher(body: S['TeacherCreate']): Promise<S['TeacherRead']> {
  return apiRequest('POST', '/api/teachers', { body })
}

/** `GET /api/teachers/{teacher_id}` · 匿名。 */
export function readTeacher(teacherId: number): Promise<S['TeacherRead']> {
  return apiRequest('GET', `/api/teachers/${teacherId}`)
}

/** `PATCH /api/teachers/{teacher_id}` · **教师头**。 */
export function updateTeacher(
  teacherId: number,
  body: S['TeacherUpdate'],
): Promise<S['TeacherRead']> {
  return apiRequest('PATCH', `/api/teachers/${teacherId}`, { body })
}

/** `DELETE /api/teachers/{teacher_id}` · **教师头** · **204**。
 *  ⚠️ `on_delete='restrict'`：有 `course_section.teacher_id` 子行 → 409 `integrity_conflict`。
 *  ⚠️ `mini_test.entered_by` 存的是**工号字符串**、不是外键，故删教师不会带走他录的小测。 */
export function deleteTeacher(teacherId: number): Promise<void> {
  return apiRequest('DELETE', `/api/teachers/${teacherId}`)
}

/** `GET /api/students` · 匿名。⚠️ 身份切换器读它拉学生名单（`limit=200`）。 */
export function listStudents(query?: PageQuery): Promise<Page<StudentListItem>> {
  return apiRequest('GET', '/api/students', { query })
}

/** `POST /api/students` · **教师头** · 201。 */
export function createStudent(body: S['StudentCreate']): Promise<S['StudentRead']> {
  return apiRequest('POST', '/api/students', { body })
}

/** `GET /api/students/{student_id}` · 匿名。 */
export function readStudent(studentId: number): Promise<S['StudentRead']> {
  return apiRequest('GET', `/api/students/${studentId}`)
}

/** `PATCH /api/students/{student_id}` · **教师头**。 */
export function updateStudent(
  studentId: number,
  body: S['StudentUpdate'],
): Promise<S['StudentRead']> {
  return apiRequest('PATCH', `/api/students/${studentId}`, { body })
}

/** `DELETE /api/students/{student_id}` · **教师头** · **204**。
 *  ⚠️ `student` 是子行最多的一张表（实测 12 个入向外键）→ 几乎一定 409。
 *  ⚠️ `notification.recipient_id` **不是**外键（多态），故 restrict 看不到那一层。 */
export function deleteStudent(studentId: number): Promise<void> {
  return apiRequest('DELETE', `/api/students/${studentId}`)
}

/** `GET /api/course-sections` · 匿名。 */
export function listCourseSections(query?: PageQuery): Promise<Page<CourseSectionListItem>> {
  return apiRequest('GET', '/api/course-sections', { query })
}

/** `POST /api/course-sections` · **教师头** · 201。
 *  ⚠️ 全表**没有唯一约束** → 这一档**没有 409**（后端走裸 `session.add`）。 */
export function createCourseSection(
  body: S['CourseSectionCreate'],
): Promise<S['CourseSectionRead']> {
  return apiRequest('POST', '/api/course-sections', { body })
}

/** `GET /api/course-sections/{course_section_id}` · 匿名。 */
export function readCourseSection(courseSectionId: number): Promise<S['CourseSectionRead']> {
  return apiRequest('GET', `/api/course-sections/${courseSectionId}`)
}

/** `PATCH /api/course-sections/{course_section_id}` · **教师头**。 */
export function updateCourseSection(
  courseSectionId: number,
  body: S['CourseSectionUpdate'],
): Promise<S['CourseSectionRead']> {
  return apiRequest('PATCH', `/api/course-sections/${courseSectionId}`, { body })
}

/** `DELETE /api/course-sections/{course_section_id}` · **教师头** · **204**。
 *  ⚠️ `restrict`：有 enrollment / class_session / alert / weekly_class_report 四个子表。 */
export function deleteCourseSection(courseSectionId: number): Promise<void> {
  return apiRequest('DELETE', `/api/course-sections/${courseSectionId}`)
}

/** `GET /api/enrollments` · 匿名。 */
export function listEnrollments(query?: PageQuery): Promise<Page<EnrollmentListItem>> {
  return apiRequest('GET', '/api/enrollments', { query })
}

/** `POST /api/enrollments` · **教师头** · 201。
 *  ⚠️ `enrollment` 今天在生产路径上**没有任何写入方**（`alert_stage` 的模块 docstring
 *  也记了同一件事），它只由 `seed_database` 与本端点铺 —— 而它是
 *  `require_teaches_student` 那道闸门的判据之一，故漏录的表现是**教师端 403**。 */
export function createEnrollment(body: S['EnrollmentCreate']): Promise<S['EnrollmentRead']> {
  return apiRequest('POST', '/api/enrollments', { body })
}

/** `GET /api/enrollments/{enrollment_id}` · 匿名。 */
export function readEnrollment(enrollmentId: number): Promise<S['EnrollmentRead']> {
  return apiRequest('GET', `/api/enrollments/${enrollmentId}`)
}

/** `PATCH /api/enrollments/{enrollment_id}` · **教师头**。 */
export function updateEnrollment(
  enrollmentId: number,
  body: S['EnrollmentUpdate'],
): Promise<S['EnrollmentRead']> {
  return apiRequest('PATCH', `/api/enrollments/${enrollmentId}`, { body })
}

/** `DELETE /api/enrollments/{enrollment_id}` · **教师头** · **204**。 */
export function deleteEnrollment(enrollmentId: number): Promise<void> {
  return apiRequest('DELETE', `/api/enrollments/${enrollmentId}`)
}

/* ==========================================================================
   spec §4.2 学期节点数据（4 个：3 可写 + 1 只读）
   ========================================================================== */

/** `GET /api/fitness-test-batches` · 匿名。 */
export function listFitnessTestBatches(
  query?: PageQuery,
): Promise<Page<FitnessTestBatchListItem>> {
  return apiRequest('GET', '/api/fitness-test-batches', { query })
}

/** `POST /api/fitness-test-batches` · **教师头** · 201。⚠️ 全表没有唯一约束 → 没有 409。 */
export function createFitnessTestBatch(
  body: S['FitnessTestBatchCreate'],
): Promise<S['FitnessTestBatchRead']> {
  return apiRequest('POST', '/api/fitness-test-batches', { body })
}

/** `GET /api/fitness-test-batches/{fitness_test_batch_id}` · 匿名。
 *  ⚠️ 参数名多一个 `e`（后端 23 行里唯一显式传 `pk_alias` 的一行）。 */
export function readFitnessTestBatch(
  fitnessTestBatchId: number,
): Promise<S['FitnessTestBatchRead']> {
  return apiRequest('GET', `/api/fitness-test-batches/${fitnessTestBatchId}`)
}

/** `PATCH /api/fitness-test-batches/{fitness_test_batch_id}` · **教师头**。 */
export function updateFitnessTestBatch(
  fitnessTestBatchId: number,
  body: S['FitnessTestBatchUpdate'],
): Promise<S['FitnessTestBatchRead']> {
  return apiRequest('PATCH', `/api/fitness-test-batches/${fitnessTestBatchId}`, { body })
}

/** `DELETE /api/fitness-test-batches/{fitness_test_batch_id}` · **教师头** · **204**。 */
export function deleteFitnessTestBatch(fitnessTestBatchId: number): Promise<void> {
  return apiRequest('DELETE', `/api/fitness-test-batches/${fitnessTestBatchId}`)
}

/** `GET /api/fitness-test-results` · 匿名。⚠️ **只读资源**（乐跑投影 + 批处理输入）。 */
export function listFitnessTestResults(
  query?: PageQuery,
): Promise<Page<FitnessTestResultListItem>> {
  return apiRequest('GET', '/api/fitness-test-results', { query })
}

/** `GET /api/fitness-test-results/{fitness_test_result_id}` · 匿名。 */
export function readFitnessTestResult(
  fitnessTestResultId: number,
): Promise<S['FitnessTestResultRead']> {
  return apiRequest('GET', `/api/fitness-test-results/${fitnessTestResultId}`)
}

/** `GET /api/body-compositions` · 匿名。 */
export function listBodyCompositions(
  query?: PageQuery,
): Promise<Page<BodyCompositionListItem>> {
  return apiRequest('GET', '/api/body-compositions', { query })
}

/** `POST /api/body-compositions` · **教师头** · 201。 */
export function createBodyComposition(
  body: S['BodyCompositionCreate'],
): Promise<S['BodyCompositionRead']> {
  return apiRequest('POST', '/api/body-compositions', { body })
}

/** `GET /api/body-compositions/{body_composition_id}` · 匿名。 */
export function readBodyComposition(bodyCompositionId: number): Promise<S['BodyCompositionRead']> {
  return apiRequest('GET', `/api/body-compositions/${bodyCompositionId}`)
}

/** `PATCH /api/body-compositions/{body_composition_id}` · **教师头**。 */
export function updateBodyComposition(
  bodyCompositionId: number,
  body: S['BodyCompositionUpdate'],
): Promise<S['BodyCompositionRead']> {
  return apiRequest('PATCH', `/api/body-compositions/${bodyCompositionId}`, { body })
}

/** `DELETE /api/body-compositions/{body_composition_id}` · **教师头** · **204**。 */
export function deleteBodyComposition(bodyCompositionId: number): Promise<void> {
  return apiRequest('DELETE', `/api/body-compositions/${bodyCompositionId}`)
}

/** `GET /api/interest-surveys` · 匿名。⚠️ list 项**不含** `dimensions` / `raw_answers`。 */
export function listInterestSurveys(query?: PageQuery): Promise<Page<InterestSurveyListItem>> {
  return apiRequest('GET', '/api/interest-surveys', { query })
}

/** `POST /api/interest-surveys` · **教师头** · 201。 */
export function createInterestSurvey(
  body: S['InterestSurveyCreate'],
): Promise<S['InterestSurveyRead']> {
  return apiRequest('POST', '/api/interest-surveys', { body })
}

/** `GET /api/interest-surveys/{interest_survey_id}` · 匿名（含两个 JSON 列）。 */
export function readInterestSurvey(interestSurveyId: number): Promise<S['InterestSurveyRead']> {
  return apiRequest('GET', `/api/interest-surveys/${interestSurveyId}`)
}

/** `PATCH /api/interest-surveys/{interest_survey_id}` · **教师头**。 */
export function updateInterestSurvey(
  interestSurveyId: number,
  body: S['InterestSurveyUpdate'],
): Promise<S['InterestSurveyRead']> {
  return apiRequest('PATCH', `/api/interest-surveys/${interestSurveyId}`, { body })
}

/** `DELETE /api/interest-surveys/{interest_survey_id}` · **教师头** · **204**。 */
export function deleteInterestSurvey(interestSurveyId: number): Promise<void> {
  return apiRequest('DELETE', `/api/interest-surveys/${interestSurveyId}`)
}

/* ==========================================================================
   spec §4.3 派生与分层（3 个，全部只读 + forbid）
   ==========================================================================
   ⚠️ 三个都是**批处理产物**：`on_delete='forbid'` → DELETE 端点根本不存在（405）。
      删它的正确方式是重放（`POST /api/pipeline/run-daily`，它按 `batch_id` 先删后算）。 */

/** `GET /api/percentile-snapshots` · 匿名。 */
export function listPercentileSnapshots(
  query?: PageQuery,
): Promise<Page<PercentileSnapshotListItem>> {
  return apiRequest('GET', '/api/percentile-snapshots', { query })
}

/** `GET /api/percentile-snapshots/{percentile_snapshot_id}` · 匿名。 */
export function readPercentileSnapshot(
  percentileSnapshotId: number,
): Promise<S['PercentileSnapshotRead']> {
  return apiRequest('GET', `/api/percentile-snapshots/${percentileSnapshotId}`)
}

/** `GET /api/derived-metrics` · 匿名。⚠️ list 项**不含** `annual_change` / `weaknesses` /
 *  `body_comp_reasons`（只有 `weakness_count` 那个数）。 */
export function listDerivedMetrics(query?: PageQuery): Promise<Page<DerivedMetricsListItem>> {
  return apiRequest('GET', '/api/derived-metrics', { query })
}

/** `GET /api/derived-metrics/{derived_metric_id}` · 匿名（含三个 JSON 列）。 */
export function readDerivedMetrics(derivedMetricId: number): Promise<S['DerivedMetricsRead']> {
  return apiRequest('GET', `/api/derived-metrics/${derivedMetricId}`)
}

/** `GET /api/stratification-results` · 匿名。⚠️ list 项**不含** `input_snapshot`，
 *  但**含** `label`（红/黄/绿），故大屏的分层分布可以直接读 list。 */
export function listStratificationResults(
  query?: PageQuery,
): Promise<Page<StratificationResultListItem>> {
  return apiRequest('GET', '/api/stratification-results', { query })
}

/** `GET /api/stratification-results/{stratification_result_id}` · 匿名。 */
export function readStratificationResult(
  stratificationResultId: number,
): Promise<S['StratificationResultRead']> {
  return apiRequest('GET', `/api/stratification-results/${stratificationResultId}`)
}

/* ==========================================================================
   spec §4.4 处方（4 个，全部只读）
   ==========================================================================
   ⚠️ `exercises` 与 `prescription-templates` 是**刻意只读**（spec §4.4 逐字：
      「这是体育专家维护的知识资产……改阈值应走版本控制与评审，不应在运行时改数据库」）。
      故管理台的「新建/编辑/删除」按钮要**不出现**（不是禁用），并说明理由
      （计划约束第 20 条）。 */

/** `GET /api/exercises` · 匿名。⚠️ list 项**不含** `targets`。 */
export function listExercises(query?: PageQuery): Promise<Page<ExerciseListItem>> {
  return apiRequest('GET', '/api/exercises', { query })
}

/** `GET /api/exercises/{exercise_id}` · 匿名（含 `targets`）。 */
export function readExercise(exerciseId: number): Promise<S['ExerciseRead']> {
  return apiRequest('GET', `/api/exercises/${exerciseId}`)
}

/** `GET /api/prescription-templates` · 匿名。 */
export function listPrescriptionTemplates(
  query?: PageQuery,
): Promise<Page<PrescriptionTemplateListItem>> {
  return apiRequest('GET', '/api/prescription-templates', { query })
}

/** `GET /api/prescription-templates/{prescription_template_id}` · 匿名。 */
export function readPrescriptionTemplate(
  prescriptionTemplateId: number,
): Promise<S['PrescriptionTemplateRead']> {
  return apiRequest('GET', `/api/prescription-templates/${prescriptionTemplateId}`)
}

/** `GET /api/prescriptions` · 匿名。⚠️ list 项排掉了全部 **5** 个 `JsonText` 列。 */
export function listPrescriptions(query?: PageQuery): Promise<Page<PrescriptionListItem>> {
  return apiRequest('GET', '/api/prescriptions', { query })
}

/** `GET /api/prescriptions/{prescription_id}` · 匿名（16 列全给）。 */
export function readPrescription(prescriptionId: number): Promise<S['PrescriptionRead']> {
  return apiRequest('GET', `/api/prescriptions/${prescriptionId}`)
}

/** `POST /api/prescriptions/{prescription_id}/overrides` · **教师头** · 200。
 *  ⚠️ `teacher_staff_no` 与 `applied_at` **由服务端填**、不在请求体里
 *  （让它们可传等于让客户端冒充别的教师、伪造时间，而 spec §7.5 把这些记录当研究数据）。
 *  ⚠️ `kind` 是枚举 `OverrideKind`（5 个值，**下划线**风格）；域外值 → 422。
 *  ⚠️ `reason` 为空由 domain 抛 `ValueError` → 422 `unprocessable_value`。 */
export function addPrescriptionOverride(
  prescriptionId: number,
  body: S['OverrideCreate'],
): Promise<S['OverrideResultRead']> {
  return apiRequest('POST', `/api/prescriptions/${prescriptionId}/overrides`, { body })
}

/** `POST /api/prescriptions/{prescription_id}/regenerate` · **教师头** · 200。 */
export function regeneratePrescription(
  prescriptionId: number,
  query?: { asOf?: string | null },
): Promise<S['PrescriptionRead']> {
  return apiRequest('POST', `/api/prescriptions/${prescriptionId}/regenerate`, {
    query: { as_of: query?.asOf },
  })
}

/** `GET /api/weekly-adjustments` · 匿名。 */
export function listWeeklyAdjustments(query?: PageQuery): Promise<Page<WeeklyAdjustmentListItem>> {
  return apiRequest('GET', '/api/weekly-adjustments', { query })
}

/** `GET /api/weekly-adjustments/{weekly_adjustment_id}` · 匿名。 */
export function readWeeklyAdjustment(
  weeklyAdjustmentId: number,
): Promise<S['WeeklyAdjustmentRead']> {
  return apiRequest('GET', `/api/weekly-adjustments/${weeklyAdjustmentId}`)
}

/* ==========================================================================
   spec §4.5 反馈三源（4 个：1 可写 + 3 只读）
   ========================================================================== */

/** `GET /api/class-sessions` · 匿名。
 *  ⚠️⚠️ 响应体里**不含 `rpe_token`**（Plan 03 收尾小修波的两半都落地了：
 *  从 `ClassSessionRead` 上摘掉 + 目录里显式 `list_exclude`）。实测键集合是
 *  `batch_id,course_section_id,id,period,rpe_opened,session_date`。 */
export function listClassSessions(query?: PageQuery): Promise<Page<ClassSessionListItem>> {
  return apiRequest('GET', '/api/class-sessions', { query })
}

/** `POST /api/class-sessions` · **教师头** · 201。
 *  ⚠️ 响应是 `ClassSessionRead`，故**也不含口令**（那一列已从读模型上摘掉）。 */
export function createClassSession(body: S['ClassSessionCreate']): Promise<S['ClassSessionRead']> {
  return apiRequest('POST', '/api/class-sessions', { body })
}

/** `GET /api/class-sessions/{class_session_id}` · 匿名。 */
export function readClassSession(classSessionId: number): Promise<S['ClassSessionRead']> {
  return apiRequest('GET', `/api/class-sessions/${classSessionId}`)
}

/** `PATCH /api/class-sessions/{class_session_id}` · **教师头**。
 *  ⚠️ 它是唯一能把 `rpe_opened` 单独翻下去的入口，而那一档会让既有口令**交不上来**
 *  （学生侧与教师侧都会得到 409 `rpe_not_opened`）。 */
export function updateClassSession(
  classSessionId: number,
  body: S['ClassSessionUpdate'],
): Promise<S['ClassSessionRead']> {
  return apiRequest('PATCH', `/api/class-sessions/${classSessionId}`, { body })
}

/** `DELETE /api/class-sessions/{class_session_id}` · **教师头** · **204**。
 *  ⚠️ **全库唯一的 `cascade`**：删课次会连带删掉这节课的 `rpe_record`
 *  （那一节课没上，学生交的快评是无效数据）。 */
export function deleteClassSession(classSessionId: number): Promise<void> {
  return apiRequest('DELETE', `/api/class-sessions/${classSessionId}`)
}

/** `POST /api/class-sessions/{class_session_id}/open-rpe` · **教师头** · 200。
 *  ⚠️ **幂等且不换口令**：已发起过时响应里的 `already_open` 为真、口令不变。
 *  ⚠️ 计划第 8 节自审第 5 条：**优先用下面的 `readRpeToken`**（它是 GET、语义对；
 *  拿 POST 当读操作使会让前端靠 `already_open` 反推「什么都没发生」）。 */
export function openRpe(classSessionId: number): Promise<S['RpeOpenResult']> {
  return apiRequest('POST', `/api/class-sessions/${classSessionId}/open-rpe`)
}

/** `GET /api/class-sessions/{class_session_id}/rpe-status` · **教师头** · 200。
 *  已提交名单 / 待交名单（`RpeStatusRead`）。 */
export function readRpeStatus(classSessionId: number): Promise<S['RpeStatusRead']> {
  return apiRequest('GET', `/api/class-sessions/${classSessionId}/rpe-status`)
}

/** `GET /api/class-sessions/{class_session_id}/rpe-token` · **教师头** · 200。
 *  ⚠️ `rpe_opened` 为假（或口令为空）→ **409 `rpe_not_opened`**（不是 404、不是 null）。
 *  ⚠️ **匿名调它是 401 `unauthenticated`**（计划 Task 5 的第 ④ 步就断这一档）。
 *  ⚠️ 这是教师端拿到口令去投屏的**首选**入口。 */
export function readRpeToken(classSessionId: number): Promise<S['RpeTokenRead']> {
  return apiRequest('GET', `/api/class-sessions/${classSessionId}/rpe-token`)
}

/** `GET /api/rpe-records` · 匿名。⚠️ **只读资源**：写入只走下面的 `submitRpe`。 */
export function listRpeRecords(query?: PageQuery): Promise<Page<RpeRecordListItem>> {
  return apiRequest('GET', '/api/rpe-records', { query })
}

/** `POST /api/rpe-records` · **学生头** · 201。
 *  ⚠️ `student_id` 与 `submitted_at` **由服务端填**，不在请求体里。
 *  ⚠️ `rpe_token` 是**学生手输**的（计划约束第 15 条），口令不对 → **403 `invalid_rpe_token`**；
 *  课次还没发起 → **409 `rpe_not_opened`**（这一档排在验口令之前）。
 *  ⚠️ 同一节课交第二次撞 DB 的 `uq_rpe_record_session_student` →
 *  **409 `integrity_conflict`**（⚠️ 计划里那个 `rpe_already_submitted` **不存在**）。 */
export function submitRpe(body: S['RpeSubmitCreate']): Promise<S['RpeRecordRead']> {
  return apiRequest('POST', '/api/rpe-records', { body })
}

/** `GET /api/rpe-records/{rpe_record_id}` · 匿名。 */
export function readRpeRecord(rpeRecordId: number): Promise<S['RpeRecordRead']> {
  return apiRequest('GET', `/api/rpe-records/${rpeRecordId}`)
}

/** `GET /api/training-logs` · 匿名。⚠️ **只读资源**：写入只走下面的 `createTrainingLog`。 */
export function listTrainingLogs(query?: PageQuery): Promise<Page<TrainingLogListItem>> {
  return apiRequest('GET', '/api/training-logs', { query })
}

/** `POST /api/training-logs` · **学生头** · 201。
 *  ⚠️ 请求体只有 5 个字段（`log_date` / `completed` / `duration_min` / `feeling` /
 *  `is_rest_day`）：`student_id` 来自请求头，`submitted_at` 与 `late` **由服务端算**
 *  （spec §8.1 的 00:00–22:00 窗口；完成率是 RCT 的关键过程指标，必须严格）。
 *  ⚠️ 撞 `(student_id, log_date)` → 409 `integrity_conflict`。 */
export function createTrainingLog(body: S['TrainingLogCreate']): Promise<S['TrainingLogRead']> {
  return apiRequest('POST', '/api/training-logs', { body })
}

/** `GET /api/training-logs/{training_log_id}` · 匿名。 */
export function readTrainingLog(trainingLogId: number): Promise<S['TrainingLogRead']> {
  return apiRequest('GET', `/api/training-logs/${trainingLogId}`)
}

/** `GET /api/mini-tests` · 匿名。⚠️ list 项**不含** `item_combo`。 */
export function listMiniTests(query?: PageQuery): Promise<Page<MiniTestListItem>> {
  return apiRequest('GET', '/api/mini-tests', { query })
}

/** `POST /api/mini-tests/batch` · **教师头** · ⚠️ **200 不是 201**（它是批量的，
 *  响应是「成功的 N 条 + 失败的 M 条」，不是单一 Location）。
 *  ⚠️ 请求体是一个**数组**（`MiniTestEntryCreate[]`），不是 `{items: [...]}`。 */
export function batchMiniTests(
  payload: S['MiniTestEntryCreate'][],
): Promise<S['MiniTestBatchResult']> {
  return apiRequest('POST', '/api/mini-tests/batch', { body: payload })
}

/** `GET /api/mini-tests/normalized` · **匿名** · 200。
 *  ⚠️⚠️ **它此前挂 `X-Teacher-Staff-No`**（教师头 200 / 学生头 401 / 匿名 401），
 *  Plan 04 Task 3 的后端小修波把那个头**摘掉了**：计划把「班内百分位」分给了
 *  **学生**页面，而 `client.ts` 一次只注入一个身份头，故「有 `studentId`」与
 *  「能读它」在结构上互斥。⚠️ 摘掉它**没有多给出一列数据**：响应里的
 *  `student_id` / `mini_test_id` / `squat_score` 三格与匿名 `GET /api/mini-tests`
 *  的 `student_id` / `id` / `squat_30s_count` 逐字相等，`shuttle_score` / `composite`
 *  是 `shuttle_20m_s` + 班内分组（匿名 `GET /api/enrollments`）的换算。
 *  守卫是后端 `tests/api/test_feedback.py` 的
 *  `test_the_normalized_route_is_anonymous_and_a_student_can_read_it`（三拍逐个对账）。
 *  ⚠️ 两个查询参数都是**必填**（`semester_id` / `week`）。
 *  ⚠️ 计划约束第 11 条：单人班的百分位后端给 `50.0`（数学上正确），
 *  但看起来像真排过名 → **`scored_count == 1` 时前端要显示「无排名」**。
 *  ⚠️ 计划约束第 12 条：**进步榜不要调本端点**，读
 *  `weekly_class_report.progress_board`（两者的算式已统一，但**窗口不同**）。 */
export function getNormalizedScores(query: {
  semesterId: number
  week: number
}): Promise<S['NormalizedScoreRead']> {
  return apiRequest('GET', '/api/mini-tests/normalized', {
    query: { semester_id: query.semesterId, week: query.week },
  })
}

/** `GET /api/mini-tests/{mini_test_id}` · 匿名（含 `item_combo`）。 */
export function readMiniTest(miniTestId: number): Promise<S['MiniTestRead']> {
  return apiRequest('GET', `/api/mini-tests/${miniTestId}`)
}

/* ==========================================================================
   spec §4.6 预警与通知（2 个，只读 + forbid）
   ========================================================================== */

/** `GET /api/alerts` · 匿名。⚠️ list 项**不含** `trigger_snapshot`。
 *  ⚠️ 计划约束第 9 条：泛型 list **没有筛选参数** —— `?rule_id=red` 会被 FastAPI
 *  **静默忽略**（不报错、只返回全量）→ 教师端的预警队列必须**客户端过滤**。 */
export function listAlerts(query?: PageQuery): Promise<Page<AlertListItem>> {
  return apiRequest('GET', '/api/alerts', { query })
}

/** `GET /api/alerts/{alert_id}` · 匿名（含 `trigger_snapshot`）。 */
export function readAlert(alertId: number): Promise<S['AlertRead']> {
  return apiRequest('GET', `/api/alerts/${alertId}`)
}

/** `POST /api/alerts/{alert_id}/handle` · **教师头** · 200。
 *  ⚠️ `action` ∈ `reduce_20pct` / `ignore` / `note`（见 `types.ts` 的 `HANDLE_ACTIONS`；
 *  ⚠️ 后端**没有**把这三档暴露成 OpenAPI 的 enum，故读不到，只能字面对拍）。
 *  ⚠️ `status != 'pending'` → **409 `alert_not_pending`**（挡的是「减量 20%」被点两次：
 *  本周训练单是该周全部 factor 的**累乘**，再点一次就是 0.64）。
 *  ⚠️ `action='note'` 而 `note` 为空 → **422 `unprocessable_value`**。
 *  ⚠️ 处置成功后**要刷新训练单**（减量已生效）。
 *  ⚠️ 响应里的 `adjustment` / `notification` **可能是 null** —— 那是有信息的一档
 *  （那一周已经有 auto 调整了，故减量没有再发生一次）。 */
export function handleAlert(
  alertId: number,
  action: HandleAction,
  options: { note?: string | null; asOf?: string | null } = {},
): Promise<S['AlertHandleResult']> {
  return apiRequest('POST', `/api/alerts/${alertId}/handle`, {
    query: { as_of: options.asOf },
    body: { action, note: options.note ?? null },
  })
}

/** `GET /api/notifications` · 匿名。
 *  ⚠️ 收件人是多态的（`recipient_kind` + `recipient_id`），而泛型 list 没有筛选参数
 *  → **它读到的是全部收件人的行**（演示库 19 条、发给 19 个不同的学生）。
 *  ⚠️ **学生端的消息中心不要再调它**：自 Plan 04 Task 3 的小修波起有了
 *  `GET /api/students/{id}/notifications`（学生头、服务端已过滤），
 *  见下面的 :func:`listStudentNotifications`。本函数保留给管理台
 *  （Task 4 要能读全部 23 个资源的列表）。 */
export function listNotifications(query?: PageQuery): Promise<Page<NotificationListItem>> {
  return apiRequest('GET', '/api/notifications', { query })
}

/** `GET /api/notifications/{notification_id}` · 匿名。 */
export function readNotification(notificationId: number): Promise<S['NotificationRead']> {
  return apiRequest('GET', `/api/notifications/${notificationId}`)
}

/** `POST /api/notifications/{notification_id}/read` · **学生头** · 200。
 *  ⚠️ 不是发给请求头里这个学生的（**或它不存在**，两档刻意同形）→ **403 `not_recipient`**。
 *  ⚠️ 它只改 `is_read`、**不删行**：`notification` 是 `on_delete='forbid'` 且刻意不带
 *  `batch_id`，故「从任何入口都删不掉一行通知」是有意的。 */
export function markNotificationRead(notificationId: number): Promise<S['NotificationRead']> {
  return apiRequest('POST', `/api/notifications/${notificationId}/read`)
}

/* ==========================================================================
   spec §4.7 班级周报（1 个，只读 + forbid）
   ========================================================================== */

/** `GET /api/weekly-class-reports` · 匿名。⚠️ list 项排掉了全部 **5** 个聚合列，
 *  只剩 `suggestion` 那一句人话 + 三个 id + 周次 + 生成时刻。
 *  ⚠️ 要那 5 个聚合列请调下面的 `getWeeklyClassReport`（特例端点）。 */
export function listWeeklyClassReports(
  query?: PageQuery,
): Promise<Page<WeeklyClassReportListItem>> {
  return apiRequest('GET', '/api/weekly-class-reports', { query })
}

/** `GET /api/weekly-class-reports/{weekly_class_report_id}` · 匿名（12 列全给）。 */
export function readWeeklyClassReport(
  weeklyClassReportId: number,
): Promise<S['WeeklyClassReportRead']> {
  return apiRequest('GET', `/api/weekly-class-reports/${weeklyClassReportId}`)
}

/* ==========================================================================
   学生侧特例端点（6 个，**学生头**）
   ========================================================================== */

/** `GET /api/students/{student_id}/home` · **学生头** · 200。
 *  ⚠️ `X-Student-Id` 必须与路径里的 `student_id` 是同一个人，否则 403 `forbidden`。 */
export function getStudentHome(
  studentId: number,
  query?: { asOf?: string | null },
): Promise<S['StudentHomeRead']> {
  return apiRequest('GET', `/api/students/${studentId}/home`, { query: { as_of: query?.asOf } })
}

/** `GET /api/students/{student_id}/weekly-sheet` · **学生头** · 200。
 *  ⚠️ 计划约束第 14 条：教师读同一份数据要走下面的 `getTeacherWeeklySheet` ——
 *  两个端点的响应体**逐字相同**（后端把函数体抽成了 `_weekly_sheet_response` 两处共用），
 *  但**挂的头不同**，教师用自己的头调本端点会 **401**。
 *  ⚠️ 没有生效处方 → 404 `no_active_prescription`；`as_of` 落在微周期之外 →
 *  404 `outside_microcycle`。
 *  ⚠️ 计划约束第 13 条：若 `reasons` 有两条而 `factor` 是 0.8，UI 要写
 *  「本周减量 20%（由 2 条红色预警触发）」—— 一处方一周至多一条 auto 调整。 */
export function getWeeklySheet(
  studentId: number,
  query?: { asOf?: string | null },
): Promise<S['WeeklySheetRead']> {
  return apiRequest('GET', `/api/students/${studentId}/weekly-sheet`, {
    query: { as_of: query?.asOf },
  })
}

/** `GET /api/students/{student_id}/prescriptions/current` · **学生头** · 200。
 *  ⚠️ 没有 → 404 `no_active_prescription`（「没有」是常态、不是故障）。
 *  ⚠️ `status='needs_review'` 的那一行**照常返回**并带着它的 `status`。 */
export function getCurrentPrescription(
  studentId: number,
  query?: { asOf?: string | null },
): Promise<S['PrescriptionRead']> {
  return apiRequest('GET', `/api/students/${studentId}/prescriptions/current`, {
    query: { as_of: query?.asOf },
  })
}

/** `GET /api/students/{student_id}/training-logs/completion-rate` · **学生头** · 200。
 *  ⚠️ 两个查询参数都是**必填**（`semester_id` / `week`）。
 *  ⚠️ 计划约束第 10 条：`completion_rate` 可能是 `null`（无处方时）→ 显示「—」，
 *  **不要**显示 `0%`。 */
export function getCompletionRate(
  studentId: number,
  query: { semesterId: number; week: number },
): Promise<S['CompletionRateRead']> {
  return apiRequest('GET', `/api/students/${studentId}/training-logs/completion-rate`, {
    query: { semester_id: query.semesterId, week: query.week },
  })
}

/* ==========================================================================
   教师侧特例端点（大屏 / 周报 / 手动跑批）
   ========================================================================== */

/** `GET /api/teacher/students/{student_id}/weekly-sheet` · **教师头** · 200。
 *  ⚠️ 计划约束第 14 条：**教师端必须走这一条**。响应体与学生侧那个逐字相同。
 *  ⚠️ 它过 `require_teaches_student`（任教关系 + 学期），故「上学期教过他」
 *  **不等于**「这学期能读他」→ 403 `forbidden`。 */
export function getTeacherWeeklySheet(
  studentId: number,
  query?: { asOf?: string | null },
): Promise<S['WeeklySheetRead']> {
  return apiRequest('GET', `/api/teacher/students/${studentId}/weekly-sheet`, {
    query: { as_of: query?.asOf },
  })
}

/** `GET /api/teacher/students/{student_id}/home` · **教师头** · 200。
 *
 *  ⚠️⚠️ **这一格是 Plan 04 收尾波新加的**（Task 3 顶回的那一条落地）。此前教师端的
 *  「学生详情」页拿不到 `/home` 那一整包：学生侧的 `GET /api/students/{id}/home`
 *  挂 `X-Student-Id`，教师用自己的头调它是 **401 `unauthenticated`**，而 `client.ts`
 *  一次只注入一个身份头 → 那一页只能降级交付（分层改走匿名的
 *  `stratification-results`、拿不到后端现算的 `explanation`，待办 / 未读数 / 勋章计数
 *  三样点名拿不到）。
 *
 *  ⚠️ **响应体与学生侧那个端点逐字相同**（后端把函数体抽成了
 *  `dashboard._student_home_response` 两处共用），故返回类型也是同一个
 *  `StudentHomeRead`（`/openapi.json` 上两个端点指向同一个 schema）。
 *  ⚠️ 它过 `require_teaches_student`（**本学期**的任教关系），故不是他本学期教的
 *  学生 → 403 `forbidden`；⚠️ 而 `weekly_sheet` 那一格在本端点里是**折成 `null`** 的
 *  （首页是一屏，一格缺数据不该让整屏失败）——要区分「没有处方」与「那一天不在
 *  微周期里」请调上面的 `getTeacherWeeklySheet`（它的两档 `code` 不同）。 */
export function getTeacherStudentHome(
  studentId: number,
  query?: { asOf?: string | null },
): Promise<S['StudentHomeRead']> {
  return apiRequest('GET', `/api/teacher/students/${studentId}/home`, {
    query: { as_of: query?.asOf },
  })
}

/** `GET /api/dashboard/class/{course_section_id}` · **教师头** · 200。
 *  ⚠️ 大屏的主端点，**现算**（不读存下来的那一行），故它随时有数。
 *  ⚠️ 它过 `require_teaches_section`：不是他任教的班（或班不存在）→ 403 `forbidden`
 *  （**两档刻意同形**，都报 403 不报 404）。 */
export function getClassDashboard(
  courseSectionId: number,
  query?: { week?: number | null; asOf?: string | null },
): Promise<S['ClassDashboardRead']> {
  return apiRequest('GET', `/api/dashboard/class/${courseSectionId}`, {
    query: { week: query?.week, as_of: query?.asOf },
  })
}

/** `GET /api/dashboard/weekly-class-report/{course_section_id}` · **教师头** · 200。
 *  ⚠️ 计划约束第 19 条：`weekly_class_report` **只在周日**生成 →
 *  那一周没有就是 **404 `no_weekly_report`**，前端要显示「本周周报将在周日生成」，
 *  **不要显示成一堆 0**。
 *  ⚠️ `suggestion` 是后端算好的一句话，**原样显示**，不要前端再判一次。
 *  ⚠️ `checkin_rate_by_layer[层].rate` 可能是 `null`（那一层没人时）→ 显示「—」。 */
export function getWeeklyClassReport(
  courseSectionId: number,
  query?: { week?: number | null },
): Promise<S['WeeklyClassReportRead']> {
  return apiRequest('GET', `/api/dashboard/weekly-class-report/${courseSectionId}`, {
    query: { week: query?.week },
  })
}

/** `POST /api/pipeline/run-daily` · **教师头** · 200。
 *  ⚠️ **演示时要慎用**（`demo.ps1:172-179` 逐字警告过）：这个端点走 `run_daily` 的
 *  **缺省** `now`（真实时钟）而不是 `business_now(as_of)`。演示库的 `as_of` 是
 *  `2025-10-12`（一个历史日），故点它一次会让 `alert.triggered_at` 落到「真实的今天」、
 *  与报表周窗口不相交，`weekly_class_report.alert_summary` 会**变回 9 个 0**。
 *  ⚠️ `business_date` 是幂等键的一半：同一天重复调用是**重放**
 *  （按 `batch_id` 先删七张表再整批重算，**不含** class_session / rpe_record /
 *  training_log / notification，故不会删掉学生刚交的快评与已推的消息）。 */
export function runDaily(body: S['RunDailyCreate']): Promise<S['RunDailyResult']> {
  return apiRequest('POST', '/api/pipeline/run-daily', { body })
}

/* ==========================================================================
   ⚠️ 学生端的两个「收集 + 客户端过滤」助手（Task 2 建三个，Task 3 的小修波收掉一个）
   ==========================================================================
   它们是计划约束第 9 条那一句的落地：

       「泛型 list 没有其它筛选参数，`GET /api/alerts?rule_id=red` 这种会被
        FastAPI **静默忽略**（不报错、只返回全量）→ 前端必须客户端过滤。」

   故「我的打卡记录」与「我的课堂快评」两件事在后端**没有**端点，只能拉全量再筛。
   ⚠️ **第三件（「发给我的通知」）自 Plan 04 Task 3 的小修波起不再走这里**：
   后端补了 `GET /api/students/{id}/notifications`（学生头），故它搬到了
   :func:`listStudentNotifications` —— 那一格是本仓「能不付客户端过滤的代价就不付」
   的第一个例子，也是**唯一**一个（`training_log` 841 行 / `rpe_record` 240 行
   仍然只能拉全量；要不要给它们也开窄端点，留给控制者裁定）。

   ⚠️ **`limit` 的上界是 200**（`deps.Page`），而演示库的 `training_log` 是 841 行、
      `rpe_record` 是 240 行 → 一页拉不完，故这里按 `offset` 翻页收集。
   ⚠️ **`cap` 是承重的**：一个没有上界的收集循环在「后端 `total` 与实际行数不符」时
      会转 forever（而那一档在真仓出现过：`total` 是过滤前数的）。撞到 cap 就停，
      并把「还有更多」如实交给调用方。
   ⚠️ 两个函数一律**保持后端给的顺序**（不按时间重排）：排序是展示层的事，
      在页面里做，于是「列表的顺序」只有一个住址。
   ========================================================================== */

/** 一页一页拉，直到收满 `total` 或撞到 `cap`。返回 `[行, 是否还有更多]`。 */
async function collectPages<T>(
  fetchPage: (query: PageQuery) => Promise<Page<T>>,
  cap: number,
): Promise<[T[], boolean]> {
  const rows: T[] = []
  let offset = 0
  let truncated = false
  for (;;) {
    const limit = Math.min(200, cap - rows.length)
    if (limit <= 0) {
      truncated = true
      break
    }
    const page = await fetchPage({ limit, offset })
    rows.push(...page.items)
    offset += page.items.length
    if (page.items.length === 0 || rows.length >= page.total) break
    if (rows.length >= cap) {
      truncated = rows.length < page.total
      break
    }
  }
  return [rows, truncated]
}

/** 学生端一次最多收集多少行。⚠️ 演示库最大的那张表是 `training_log`（840 行）。 */
export const STUDENT_LIST_CAP = 1200

/** `GET /api/training-logs` 翻页收集 → 只留 `student_id === 我` 的那些。
 *  ⚠️ 打卡页读它渲染「本周已打卡」并据此挡掉一次必然 409 的提交
 *  （`uq_training_log_student_day`：一天一行，重复 → 409 `integrity_conflict`）。 */
export async function listMyTrainingLogs(
  studentId: number,
  cap: number = STUDENT_LIST_CAP,
): Promise<{ items: TrainingLogListItem[]; truncated: boolean }> {
  const [rows, truncated] = await collectPages<TrainingLogListItem>(listTrainingLogs, cap)
  return { items: rows.filter((row) => row.student_id === studentId), truncated }
}

/** `GET /api/rpe-records` 翻页收集 → 只留我的那些。⚠️ `RpeTrend.vue` 的唯一数据源。 */
export async function listMyRpeRecords(
  studentId: number,
  cap: number = STUDENT_LIST_CAP,
): Promise<{ items: RpeRecordListItem[]; truncated: boolean }> {
  const [rows, truncated] = await collectPages<RpeRecordListItem>(listRpeRecords, cap)
  return { items: rows.filter((row) => row.student_id === studentId), truncated }
}

/** `GET /api/students/{student_id}/notifications` · **学生头** · 200。
 *
 *  ⚠️⚠️ **这一格是 Plan 04 Task 3 的后端小修波新加的**（Task 2 顶回的第 1 处，
 *  控制者裁定「补上」）。加它的理由**不是**堵洞 —— `GET /api/notifications`
 *  今天仍然是匿名的、仍然一次能读到全部 19 条，那是本仓「读 ⇒ 一律匿名」的既有口径
 *  （那一堆匿名 GET 里已经包括 `GET /api/students`，它给的是 60 个人的出生日期；
 *  ⚠️ 具体多少个匿名 GET **刻意不写在这里**——机器口径见本文件头注释第 1 条）。
 *  理由是**前端的代价**：泛型 list 没有筛选参数，故「发给我的消息」此前只能是
 *  「拉全表 + 客户端过滤」。能不付的代价就不付。
 *
 *  ⚠️ **响应体是一个裸数组**、不是 `{items, limit, offset, total}`：本端点没有分页参数
 *  （演示库上 19 条通知发给 19 个**不同**的学生，即一人一条），后端刻意不回
 *  三个没有信息的键。⚠️ 于是它是全仓第一个回裸数组的读端点，故这里的返回类型
 *  是 `NotificationListItem[]` 而不是 `Page<…>`。
 *  ⚠️ **排序在服务端**（`created_at` 降序、同刻按 `id` 降序），故页面**不要**再
 *  `.sort()` 一遍 —— 「新的在上面」这件事现在只有一个住址。
 *  ⚠️ 每一项的键集合与 `NotificationListItem`（= `NotificationRead` 的 10 列）
 *  **逐字相同**：守卫是后端
 *  `tests/api/test_dashboard.py::test_the_notification_list_returns_only_the_requesters_rows_newest_first`
 *  （它从 `/openapi.json` 实读那 10 列、与响应体对账）。
 *  ⚠️ 越权（学生 A 用 B 的身份头读 B 的）→ **403 `forbidden`**；缺头 → **401**；
 *  教师头 → **401**（本端点只做学生侧）。 */
export function listStudentNotifications(studentId: number): Promise<NotificationListItem[]> {
  return apiRequest('GET', `/api/students/${studentId}/notifications`)
}

/** 「发给我的站内消息」。⚠️ **签名与 Task 2 交付时逐字相同**（`Notifications.vue`
 *  因此一行都没改数据接线），变的只有函数体：
 *  它此前是「`GET /api/notifications` 翻页收集 + 客户端过滤 `recipient_kind` /
 *  `recipient_id`」，现在走上面那个**服务端已过滤**的窄端点。
 *
 *  ⚠️ `cap` 与 `truncated` **保留**：它们现在是「客户端的安全上限」而不是
 *  「翻页收集撞到上限」。后端不给分页，故 `truncated` 只可能在
 *  「一个学生的消息多到超过 `cap`」时为真 —— 演示库上恒为 `false`
 *  （一人一条）。留着它的理由：`Notifications.vue` 读 `data.truncated` 渲染一句
 *  警告，删掉这个键就要改那个页面，而「签名不变」正是本波的要求。 */
export async function listMyNotifications(
  studentId: number,
  cap: number = STUDENT_LIST_CAP,
): Promise<{ items: NotificationListItem[]; truncated: boolean }> {
  const rows = await listStudentNotifications(studentId)
  return { items: rows.slice(0, cap), truncated: rows.length > cap }
}

/* ==========================================================================
   ⚠️ 管理台的**泛型 CRUD**（Task 4 加的一组；与本文件顶部那句「不做通用工厂」
      **不矛盾** —— 见下面那段理由）
   ==========================================================================
   本文件顶部逐字写了「92 个操作里只有 23 个是同形的，故一个端点一个函数」。
   那句话说的是**学生端与教师端**：它们调的是 69 个各不相同的特例端点，
   给它们套工厂换来的是一层抽象而不是能力。

   而管理台恰好是**剩下的那 23 个同形的**：它对着 `catalog/resources.ts` 的
   23 行、用**一套**页面渲染任何一个资源（计划 Task 4 逐字：「不要手写 23 套页面」）。
   一个数据驱动的页面**没法**在编译期写死 `listSemesters` / `listTeachers` / …
   —— 它拿到的是一个 `resource: string`。故这一组泛型函数是那一页的**接口**，
   不是对上面 97 个具名函数的重复：具名函数给「知道自己在调哪个端点」的页面用
   （有类型、IDE 补得出参数名），这一组给「不知道也不该知道」的管理台用。

   ⚠️ **返回类型是 `Record<string, unknown>` 而不是 `S['*Read']`**：
   23 个 `*Read` 各不相同，而调用方手里只有一个 `resource` 串，无法把泛型形参钉住。
   管理台因此**逐格渲染**（`Object.entries` + `present.ts` 的中文标签），
   它本来就不该对某一列做特化 —— 那是「23 套页面」的开端。
   ⚠️ `listResource` 是唯一保留强类型的一格：`ListItemByResource[R]` 让它
   在 `R` 是字面量时仍然精确（目录页与守卫都靠这一格）。
   ========================================================================== */

/** `GET /api/<resource>` · **匿名** · 分页信封 4 个键。
 *  ⚠️ 只有 `limit` / `offset` 两个参数；`?level=red` 这类会被 FastAPI **静默忽略**
 *  （约束第 9 条）→ 要筛一律在客户端筛。 */
export function listResource<R extends ResourceName>(
  resource: R,
  query?: PageQuery,
): Promise<Page<ListItemByResource[R]>> {
  return apiRequest('GET', `/api/${resource}`, { query })
}

/** `GET /api/<resource>/{pk}` · **匿名** · 含被 list 排掉的那些 `JsonText` 列。 */
export function readResource(resource: string, id: number): Promise<Record<string, unknown>> {
  return apiRequest('GET', `/api/${resource}/${id}`)
}

/** `POST /api/<resource>` · ⚠️ **教师头** · 201。
 *  匿名 → **401 `unauthenticated`**（fix 波 1 给 9 个可写资源的写入侧全挂上了
 *  `require_teacher`）；只读资源 → **405 `http_405`**（端点根本不注册）。 */
export function createResource(
  resource: string,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return apiRequest('POST', `/api/${resource}`, { body })
}

/** `PATCH /api/<resource>/{pk}` · ⚠️ **教师头**。
 *  ⚠️ **只传要改的那几格**（`undefined` 的键由 `contract.ts` 的 `fromInputValue`
 *  就地丢掉，不会变成 `null` 送上来）：
 *  PATCH 的语义是「只改传上来的」，把整行 read-one 的结果原样送回去会让
 *  `id` 这类**只在 `*Read` 上、不在 `*Update` 上**的列出现在请求体里
 *  （Pydantic 会把它丢掉，但「前端送了一份后端不认的列」这件事本身就是要避免的形状）。
 *  ⚠️ 实测 9 个可写资源：`*Update` 的字段集与 `*Create` **逐字相等**、
 *  `required` **全是 `[]`**，而 `*Read` = `*Create` + `id`。 */
export function updateResource(
  resource: string,
  id: number,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  return apiRequest('PATCH', `/api/${resource}/${id}`, { body })
}

/** `DELETE /api/<resource>/{pk}` · ⚠️ **教师头** · **204**（`client.ts` 不解析 body）。
 *
 *  ⚠️ **只有 8 个资源有这个端点**（实测自 `/openapi.json`）：
 *  `teachers` / `students` / `course-sections` / `enrollments` /
 *  `fitness-test-batches` / `body-compositions` / `interest-surveys` / `class-sessions`。
 *  - `on_delete='forbid'` 的 **10** 个（含可写的 `semesters`）**根本不注册** DELETE
 *    → 打过去是 **405 `http_405`**。故按钮**不出现**（`hasDeleteEndpoint` 就是这一格）。
 *  - `on_delete='restrict'` 的资源删一行**被子表指着**的行 → **409 `integrity_conflict`**，
 *    而「被谁引用」在 `message` 里（后端点名了子表），**不在 `detail` 里**。
 *  - `on_delete='cascade'` 的全库只有 **1** 个：`class-sessions`
 *    （删一节课 → 这节课的 `rpe_record` 一并作废）。故删除前要**二次确认**。 */
export function deleteResource(resource: string, id: number): Promise<void> {
  return apiRequest('DELETE', `/api/${resource}/${id}`)
}

