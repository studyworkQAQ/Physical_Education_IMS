<script setup lang="ts">
/**
 * `views/teacher/AlertQueue.vue` —— **预警队列 + 处置**（`/t/alerts`）。
 *
 * ---------------------------------------------------------------------------
 * 读的端点（⚠️ 全部实测过）
 * ---------------------------------------------------------------------------
 *  1. `GET /api/alerts?limit=200` · ⚠️ **教职会话**（`read_scope="staff_taught"`，
 *     Plan 06 Task 8）—— ⚠️ **不再是全校全量**：教师只读得到
 *     **自己本学期任教班级的学生**那些行（演示库实测：全表 32 行，
 *     T0001 读到 21 行、T0002 读到 22 行）。⚠️ list 项**不含** `trigger_snapshot`，
 *     那是 8 个「list 比 `*Read` 少列」的资源之一；
 *     ⚠️⚠️ **Plan 06 Task 8b 给它补了第二根轴**：一行**没有**学生所有者的预警
 *     （= 班级级，`student_id IS NULL` + `course_section_id` 非空）改按
 *     「那个班是不是我**本学期**任教的」判，故我任教班自己的班级级预警也在里面
 *     （别的班的、以及不带任何班的教师，仍然读不到）。⚠️ 演示库上那一类行是 **0**，
 *     故上面那两个数（21 / 22）**一个都没变**——本页在演示库上的渲染结果因此
 *     与 Task 8 逐字相同，变的是「一旦有班级级预警」时的行为。
 *  2. `GET /api/teachers` / `GET /api/course-sections` / `GET /api/students` ·
 *     **教职会话 / 匿名** —— 工号 → `teacher.id` → 「我任教的班」→ 名册；
 *     以及 id → 姓名/班名（⚠️ 两份名册是 `read_scope="staff"`：教职全读，
 *     故教师仍然能看到全校的学生姓名 —— 那是「按工号与姓名显示」的需要，
 *     而**健康档案**那一圈已经收窄了）；
 *  3. `GET /api/enrollments?limit=200` · ⚠️ **教职会话**（`staff_taught`）——
 *     名册（预警的班级归属靠它反查）；⚠️ 它自己也已经收窄到「我的学生」，
 *     故 `sectionsOfStudent` 对**我任教的班**是完整的（那正是本页要的）；
 *  4. `POST /api/alerts/{alert_id}/handle` · ⚠️ **教师头** —— 三档动作；
 *  5. `GET /api/teacher/students/{id}/weekly-sheet?as_of=` · ⚠️ **教师头** ——
 *     处置成功之后**回读训练单**，把「减量已生效」这件事拿给教师看
 *     （⚠️ 走 `/api/teacher/...` 那一个变体，学生侧那个挂学生头 → 401，约束第 14 条）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ 客户端过滤（计划约束第 9 条）
 * ---------------------------------------------------------------------------
 * 泛型 list **没有筛选参数**：`GET /api/alerts?level=red` 会被 FastAPI
 * **静默忽略**（不报错、只返回全量）。故 `level` / `status` / 班级归属三档筛选
 * 一律在**客户端**做。⚠️ 本页把这件事写在页面上（不是藏在代码里）：
 * 一个「筛了但后端没筛」的界面在演示时会让人以为后端支持筛选参数。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ 演示库的实测口径（派单第 2 条顶回：预警是 30 行不是 11 行）
 * ---------------------------------------------------------------------------
 * `red 11 + green 13 + yellow 6 = 30`，**全 `pending`**、**全学生级**
 * （`course_section_id` 为 `null`、`student_id` 非空；实测
 * `course_section_id` 非空的行数是 **0**）。
 * ⚠️ 两个后果，本页都要如实处置：
 *  1. 计划 Task 3 的验收写「能看到 11 条预警」—— **11 是红色的那一档**，
 *     总数是 30。故本页的缺省视图是「全部 30 行」，并把三档计数摆在最上面；
 *  2. **「班级级」筛选档在演示库上恒为空**。班级级的规则是
 *     `YELLOW_CLASS_RPE_HIGH`（班级 RPE 均值 > 7），而演示库上班级均值最高是
 *     **6.93 < 7.0** → 一行都没触发。故那一档必须**优雅地显示空态**
 *     （并说清为什么），不能看起来像坏了。
 *     ⚠️⚠️ **而这一档空的理由自 Plan 06 Task 8b 起只剩上面这一个**：Task 8 曾经
 *     还有第二个理由（「就算触发了教师也读不到」——那一类行 `student_id IS NULL`，
 *     而 `staff_taught` 按学生键收窄），那是 Task 8 登记在案的一格 **Critical**，
 *     本波已修（后端补了第二根轴：该班的任课教师读得到）。⚠️ 于是页面上那两处
 *     文案（「为什么这四档筛选在客户端做」那段 + 班级级空态那段）都改写过：
 *     文案不许撒谎，而「教师读不到」这句话今天已经是假的。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 三档动作与它们的失败码
 * ---------------------------------------------------------------------------
 * 三个按钮的字面值与中文都从 `present.ts` 的 `HANDLE_ACTION_OPTIONS` 来
 * （**单一所有者**；⚠️ 三档**读不到契约** —— `AlertHandleCreate.action` 在
 * OpenAPI 里逐字是 `{"type":"string"}`，闸门是 `field_validator`、不进 JSON Schema，
 * 故只能字面写出，Task 5 会加一条对拍守卫）。
 *  - `status != 'pending'` 时 `handle` → **409 `alert_not_pending`**
 *    （挡的是「减量 20%」被点两次：本周训练单是该周全部 factor 的**累乘**，
 *    再点一次就是 0.64）；
 *  - `action='note'` 而 `note` 为空白 → **422 `unprocessable_value`**；
 *  - ⚠️ `reduce_20pct` 的响应里 `adjustment` **可能是 `null`** —— 那是**有信息的一档**：
 *    一处方一周至多一条 `source='auto'` 的调整，那一周已经减过时不再减
 *    （HTTP 仍是 200、`status` 仍变 `handled`）。本页把那一档渲染成
 *    「本周已经减过量了，本次未再减」，**不是**渲染成失败。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 计划约束第 13 条：两条红色预警、一个 20% 的减量
 * ---------------------------------------------------------------------------
 * 同一周命中两条红色规则时，`alert` 表有**两行**、教师端的队列看得见两条，
 * 而训练单上只有**一个** 20% 的减量。这不是 bug，故本页在处置完第二条时
 * 会把训练单上那句 `factorSentenceOf(...)`（「本周减量 20%（由 N 条红色预警触发）」）
 * 原样显示出来 —— 让教师**看见**「我点了两次，量只减了一次」。
 */
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ApiError } from '../../api/client'
import {
  getTeacherWeeklySheet,
  handleAlert,
  listAlerts,
  listCourseSections,
  listEnrollments,
  listOnePage,
  listStudents,
  listTeachers,
  truncationNoteOf,
} from '../../api/endpoints'
import type { components } from '../../api/generated/schema'
import type { AlertListItem } from '../../api/types'
import SectionHead from '../../components/SectionHead.vue'
import TeacherNav from '../../components/TeacherNav.vue'
import { useAsync } from '../../composables/useAsync'
import {
  HANDLE_ACTION_OPTIONS,
  UNKNOWN,
  actionZh,
  alertLevelZh,
  alertStatusZh,
  factorSentenceOf,
  factorToneOf,
  groupingModeZh,
  levelOf,
  num,
  reasonZh,
  stampOf,
  volumeUnitZh,
} from '../../present'
import { useIdentityStore } from '../../stores/identity'
import type { HandleAction } from '../../api/types'

type Sheet = components['schemas']['WeeklySheetRead']

const identity = useIdentityStore()

interface Loaded {
  alerts: AlertListItem[]
  nameOf: Map<number, string>
  sectionNameOf: Map<number, string>
  sectionOf: Map<number, string>
  /** 我任教的班的 id 集合。 */
  mySections: Set<number>
  /** 学号 → 它所在的那些班（⚠️ 演示库上每个学生**恰好 2 个**：行政班 + 分层班）。 */
  sectionsOfStudent: Map<number, number[]>
  meStaffNo: string
  meName: string | null
  /** ⚠️ 单页取值被截断时**给用户看的那一句**（Plan 06 Task 11 / B4）；
   *  `null` = 一页取全了、模板一个字节都不渲染（故今天的显示结果一格都没变）。 */
  truncation: string | null
}

const { data, loading, settled, reload } = useAsync<Loaded | null>(async () => {
  const staffNo = identity.teacherStaffNo
  const [alerts, students, sections, teachers, enrollments] = await Promise.all([
    listOnePage(listAlerts, '预警'),
    listOnePage(listStudents, '学生名册'),
    listOnePage(listCourseSections, '教学班'),
    listOnePage(listTeachers, '教师名册'),
    listOnePage(listEnrollments, '选课名册'),
  ])
  const me = teachers.items.find((t) => t.staff_no === staffNo) ?? null
  const sectionsOfStudent = new Map<number, number[]>()
  for (const row of enrollments.items) {
    const list = sectionsOfStudent.get(row.student_id) ?? []
    list.push(row.course_section_id)
    sectionsOfStudent.set(row.student_id, list)
  }
  return {
    alerts: alerts.items,
    nameOf: new Map(students.items.map((s) => [s.id, s.name])),
    sectionNameOf: new Map(sections.items.map((s) => [s.id, s.name])),
    sectionOf: new Map(
      sections.items.map((s) => [
        s.id,
        `${s.name}（${groupingModeZh(s.grouping_mode)}）`,
      ]),
    ),
    mySections: new Set(
      sections.items.filter((s) => me !== null && s.teacher_id === me.id).map((s) => s.id),
    ),
    sectionsOfStudent,
    meStaffNo: staffNo ?? '',
    meName: me?.name ?? null,
    truncation: truncationNoteOf([alerts, students, sections, teachers, enrollments]),
  }
})

watch([() => identity.teacherStaffNo, () => identity.asOf], () => void reload())

/* ==========================================================================
   筛选（⚠️ 一律客户端：泛型 list 没有筛选参数）
   ========================================================================== */

type LevelFilter = 'all' | 'red' | 'yellow' | 'green'
type StatusFilter = 'all' | 'pending' | 'handled' | 'ignored'
/** `mine` = 我任教的班（按名册反查）；`section` = **班级级**的预警；`student` = 学生级。 */
type ScopeFilter = 'all' | 'mine' | 'student' | 'section'

const levelFilter = ref<LevelFilter>('all')
const statusFilter = ref<StatusFilter>('all')
const scopeFilter = ref<ScopeFilter>('all')
const sectionFilter = ref<number | 'all'>('all')

const LEVELS: readonly LevelFilter[] = ['all', 'red', 'yellow', 'green']
const STATUSES: readonly StatusFilter[] = ['all', 'pending', 'handled', 'ignored']
const SCOPES: readonly ScopeFilter[] = ['all', 'mine', 'student', 'section']

const LEVEL_ZH: Record<LevelFilter, string> = {
  all: '全部等级',
  red: '红色',
  yellow: '黄色',
  green: '绿色',
}
const STATUS_ZH: Record<StatusFilter, string> = {
  all: '全部状态',
  pending: '待处理',
  handled: '已处理',
  ignored: '已忽略',
}
const SCOPE_ZH: Record<ScopeFilter, string> = {
  all: '全部',
  mine: '我任教的班',
  student: '学生级',
  section: '班级级',
}

/** ⚠️ **筛选档可以从 URL 初始化**（`?level=red&status=pending&scope=section&section=1`）。
 *
 *  加这一格的两个理由，第二个是承重的：
 *  1. 一条「只看红色的待处理」的链接是可以分享的（教师之间转一条 URL 比转一段
 *     「你去点等级红色再点状态待处理」靠谱）；
 *  2. **它让「班级级筛选档的空态」变成可取证的**。派单逐字要求那一档
 *     「要能优雅地显示空态，不要看起来像坏了」，而 `--dump-dom` 的无头取证
 *     **点不了按钮** —— 没有这一格，那个空态就只能靠读代码断言它存在，
 *     而不能拿出它真的渲染出来的证据。
 *  ⚠️ 不合格的值一律退回 `'all'`（与 `stores/identity.ts` 的 `adoptFromUrl` 同一条口径：
 *  一个垃圾值被存下来的失效形态是「之后每一次刷新都筛出 0 行」，而真因藏在 URL 里）。 */
const route = useRoute()

function pick<T extends string>(raw: unknown, allowed: readonly T[], fallback: T): T {
  return typeof raw === 'string' && (allowed as readonly string[]).includes(raw)
    ? (raw as T)
    : fallback
}

levelFilter.value = pick(route.query.level, LEVELS, 'all')
statusFilter.value = pick(route.query.status, STATUSES, 'all')
scopeFilter.value = pick(route.query.scope, SCOPES, 'all')
{
  const raw = Number(route.query.section)
  sectionFilter.value = Number.isInteger(raw) && raw > 0 ? raw : 'all'
}

const all = computed<AlertListItem[]>(() => data.value?.alerts ?? [])

/** 三档计数（⚠️ 在**全部** 30 行上数，不是在当前筛选结果上数 —— 教师要先看见全貌）。 */
const totals = computed(() => {
  const byLevel = { red: 0, yellow: 0, green: 0 }
  const byStatus = { pending: 0, handled: 0, ignored: 0 }
  let studentLevel = 0
  let sectionLevel = 0
  for (const a of all.value) {
    if (a.level in byLevel) byLevel[a.level as keyof typeof byLevel] += 1
    if (a.status in byStatus) byStatus[a.status as keyof typeof byStatus] += 1
    if (a.course_section_id === null) studentLevel += 1
    else sectionLevel += 1
  }
  return { byLevel, byStatus, studentLevel, sectionLevel, total: all.value.length }
})

/** 一行预警**归属**哪些班。⚠️ 学生级的预警 `course_section_id` 为 `null`，
 *  故归属只能按选课关系反查（一个学生可能在两个班里 → 两个班都算它的）。 */
function sectionsOfAlert(a: AlertListItem): number[] {
  if (a.course_section_id !== null) return [a.course_section_id]
  if (a.student_id === null) return []
  return data.value?.sectionsOfStudent.get(a.student_id) ?? []
}

const rows = computed<AlertListItem[]>(() => {
  const mine = data.value?.mySections ?? new Set<number>()
  return all.value.filter((a) => {
    if (levelFilter.value !== 'all' && a.level !== levelFilter.value) return false
    if (statusFilter.value !== 'all' && a.status !== statusFilter.value) return false
    const sections = sectionsOfAlert(a)
    if (scopeFilter.value === 'student' && a.course_section_id !== null) return false
    if (scopeFilter.value === 'section' && a.course_section_id === null) return false
    if (scopeFilter.value === 'mine' && !sections.some((id) => mine.has(id))) return false
    if (sectionFilter.value !== 'all' && !sections.includes(sectionFilter.value)) return false
    return true
  })
})

const LEVEL_ORDER = ['red', 'yellow', 'green'] as const

/** 排序：红→黄→绿，再按触发时刻降序。⚠️ 排序住在页面（`endpoints.ts` 同一条口径）。 */
const sorted = computed<AlertListItem[]>(() =>
  [...rows.value].sort(
    (a, b) =>
      LEVEL_ORDER.indexOf(a.level as (typeof LEVEL_ORDER)[number]) -
        LEVEL_ORDER.indexOf(b.level as (typeof LEVEL_ORDER)[number]) ||
      b.triggered_at.localeCompare(a.triggered_at) ||
      a.id - b.id,
  ),
)

function nameOfStudent(id: number | null): string {
  if (id === null) return UNKNOWN
  return data.value?.nameOf.get(id) ?? `学生 #${id}`
}

function subjectOf(a: AlertListItem): string {
  if (a.student_id !== null) return nameOfStudent(a.student_id)
  if (a.course_section_id !== null) {
    return data.value?.sectionOf.get(a.course_section_id) ?? `教学班 #${a.course_section_id}`
  }
  return UNKNOWN
}

/* ==========================================================================
   处置
   ========================================================================== */

const busyId = ref<number | null>(null)
/** 每行的结果（成功的一档要显示 `adjustment` 是不是 `null`）。 */
interface HandleOutcome {
  alertId: number
  action: string
  ok: boolean
  /** `reduce_20pct` 那一档：`adjustment === null` 是**有信息的一档**。 */
  adjustmentWritten: boolean | null
  notificationSent: boolean | null
  status: string | null
  error: ApiError | null
  /** 处置之后回读的训练单（教师侧变体）。 */
  sheet: Sheet | null
  sheetError: ApiError | null
}
const outcomes = ref<Map<number, HandleOutcome>>(new Map())

/** 「记一笔备注」的输入框（⚠️ 只有 `note` 那一档要，且为空会 422）。 */
const noteDraft = ref<Map<number, string>>(new Map())

function noteOf(id: number): string {
  return noteDraft.value.get(id) ?? ''
}

function setNote(id: number, value: string): void {
  noteDraft.value.set(id, value)
  // ⚠️ 触发响应式：Map 的就地 set 在 Vue 3 里是响应式的，但 `noteDraft.value` 的
  //    引用没变，故这里显式换一个引用（与 `outcomes` 同一条处置）。
  noteDraft.value = new Map(noteDraft.value)
}

async function submit(alert: AlertListItem, action: HandleAction): Promise<void> {
  if (busyId.value !== null) return
  const note = noteOf(alert.id).trim()
  busyId.value = alert.id
  try {
    const result = await handleAlert(alert.id, action, { note, asOf: identity.asOf })
    const studentId = result.alert.student_id
    let sheet: Sheet | null = null
    let sheetError: ApiError | null = null
    // ⚠️ 派单逐字要求：**处置成功后要刷新训练单**（减量已生效）。
    //    走 `/api/teacher/students/{id}/weekly-sheet`（教师头），不是学生侧那个变体。
    if (studentId !== null) {
      try {
        sheet = await getTeacherWeeklySheet(studentId, { asOf: identity.asOf })
      } catch (err) {
        // ⚠️ 训练单读不到**不该**盖掉「处置成功了」这件事：两档 404
        //    （`no_active_prescription` / `outside_microcycle`）是常态。
        sheetError = err instanceof ApiError ? err : null
        if (!(err instanceof ApiError)) console.error('[weekly-sheet]', err)
      }
    }
    const outcome: HandleOutcome = {
      alertId: alert.id,
      action,
      ok: true,
      adjustmentWritten: result.adjustment === null ? false : true,
      notificationSent: result.notification === null ? false : true,
      status: result.alert.status,
      error: null,
      sheet,
      sheetError,
    }
    outcomes.value = new Map(outcomes.value).set(alert.id, outcome)
    // ⚠️ 重读列表：`status` / `handled_action` / `handled_at` 都变了，
    //    而就地改一行会让「列表里的这一行」与「后端的那一行」变成两个住址。
    await reload()
  } catch (err) {
    const outcome: HandleOutcome = {
      alertId: alert.id,
      action,
      ok: false,
      adjustmentWritten: null,
      notificationSent: null,
      status: null,
      error: err instanceof ApiError ? err : null,
      sheet: null,
      sheetError: null,
    }
    outcomes.value = new Map(outcomes.value).set(alert.id, outcome)
    if (!(err instanceof ApiError)) console.error('[handle]', err)
  } finally {
    busyId.value = null
  }
}

/** 训练量按单位分列（⚠️ 不跨单位求和：`prescription_stage.py:411-417` 逐字禁止）。 */
function volumesOf(sheet: Sheet): { unit: string; total: number }[] {
  const byRef = new Map<string, { volume: number; unit: string }>()
  for (const session of sheet.sessions) {
    for (const block of session.blocks) {
      const prev = byRef.get(block.exercise_ref)
      if (!prev || block.weekly_volume > prev.volume) {
        byRef.set(block.exercise_ref, { volume: block.weekly_volume, unit: block.volume_unit })
      }
    }
  }
  const byUnit = new Map<string, number>()
  for (const entry of byRef.values()) {
    // ⚠️ `unspecified` 不进合计（「没指定」不是「0 分钟」）
    if (entry.unit === 'unspecified') continue
    byUnit.set(entry.unit, (byUnit.get(entry.unit) ?? 0) + entry.volume)
  }
  return [...byUnit.entries()]
    .map(([unit, total]) => ({ unit, total }))
    .filter((row) => row.total > 0)
    .sort((a, b) => b.total - a.total)
}
</script>

<template>
  <div class="t-page">
    <TeacherNav />

    <!-- ⚠️ Plan 06 Task 11 / B4：单页取值被截断时**必须**让用户看见。
         判据与那句话的唯一住址是 `api/endpoints.ts` 的 `listOnePage` /
         `truncationNoteOf`；本处只负责把它画出来（用既有的 note 类，
         ⚠️ 不引新 CSS ⇒ `check:tokens` 一格都不退）。 -->
    <p v-if="data?.truncation" class="t-block__note">{{ data.truncation }}</p>

    <header class="t-head">
      <div>
        <p class="caps t-head__kicker">
          ALERT QUEUE · 客户端过滤 · {{ identity.asOf }} ·
          {{ data?.meStaffNo ?? UNKNOWN }}
          <template v-if="data?.meName">（{{ data.meName }}）</template>
        </p>
        <h2 class="zh-title t-head__title">预警队列</h2>
        <p class="t-head__meta">
          共 <strong class="num">{{ totals.total }}</strong> 条 ·
          红 <strong class="num">{{ totals.byLevel.red }}</strong> /
          黄 <strong class="num">{{ totals.byLevel.yellow }}</strong> /
          绿 <strong class="num">{{ totals.byLevel.green }}</strong> ·
          待处理 <strong class="num">{{ totals.byStatus.pending }}</strong> /
          已处理 <strong class="num">{{ totals.byStatus.handled }}</strong> /
          已忽略 <strong class="num">{{ totals.byStatus.ignored }}</strong> ·
          学生级 <strong class="num">{{ totals.studentLevel }}</strong> /
          班级级 <strong class="num">{{ totals.sectionLevel }}</strong>
        </p>
        <!-- ⚠️ Plan 06 Task 8：这一句是**新加的**，而它必须写在页面上（不是藏在代码里）。
             `GET /api/alerts` 从此按任教范围收窄，于是「共 N 条」里的 N 不再是全校的
             条数（演示库实测：全表 32 条，T0001 读到 21 条）。不说清的话，
             两位教师在同一屏上会看到两个不同的 N，而他们无从判断谁的是对的。
             ⚠️ Plan 06 Task 8b 又给「范围」补了半句：后端同时放开了
             「我任教班自己的**班级级**预警」（改前那一类行对任何教师都不可见），
             故这一句必须跟着说清，否则「归属 → 班级级」那一档一旦有行，
             页面上的范围说明就少讲了一半。 -->
        <p class="t-head__scope">
          ⚠️ 范围：<strong>我本学期任教班级的学生</strong>（不是全校），
          <strong>外加我任教班自己的班级级预警</strong>。
          后端 <code>GET /api/alerts</code> <strong>已经在 SQL 层</strong>按
          「选课名册 ⋈ 这个班的任课教师」收窄（判据在 spec §13.4.7），
          故上面的 <strong class="num">{{ totals.total }}</strong> 与「归属 → 全部」
          那一档的计数都是<strong>我这一个范围</strong>里的。管理员登录看到的是全校。
        </p>
      </div>
      <RouterLink class="btn" to="/t/dashboard">← 回大屏</RouterLink>
    </header>

    <div v-if="loading && !settled" class="t-loading">
      <span class="t-loading__rule" aria-hidden="true"></span>
      <span>正在读预警…</span>
    </div>

    <template v-else>
      <!-- 01 · 筛选（⚠️ 一律客户端） -->
      <section class="t-card">
        <SectionHead :index="1" label="FILTERS" />
        <div class="t-filters">
          <div class="t-filtergroup">
            <span class="caps t-filtergroup__label">等级</span>
            <button
              v-for="lv in LEVELS"
              :key="lv"
              type="button"
              class="t-chip"
              :class="{ 't-chip--on': levelFilter === lv }"
              @click="levelFilter = lv"
            >
              {{ LEVEL_ZH[lv] }}
            </button>
          </div>
          <div class="t-filtergroup">
            <span class="caps t-filtergroup__label">状态</span>
            <button
              v-for="st in STATUSES"
              :key="st"
              type="button"
              class="t-chip"
              :class="{ 't-chip--on': statusFilter === st }"
              @click="statusFilter = st"
            >
              {{ STATUS_ZH[st] }}
            </button>
          </div>
          <div class="t-filtergroup">
            <span class="caps t-filtergroup__label">归属</span>
            <button
              v-for="sc in SCOPES"
              :key="sc"
              type="button"
              class="t-chip"
              :class="{ 't-chip--on': scopeFilter === sc }"
              @click="scopeFilter = sc"
            >
              {{ SCOPE_ZH[sc] }}
            </button>
          </div>
          <div class="t-filtergroup">
            <span class="caps t-filtergroup__label">教学班</span>
            <select v-model="sectionFilter" class="select t-select">
              <option value="all">全部教学班</option>
              <option
                v-for="[id, label] in data?.sectionOf ?? new Map()"
                :key="id"
                :value="id"
              >
                #{{ id }} · {{ label }}
              </option>
            </select>
          </div>
        </div>
        <p class="t-block__why">
          ⚠️ 这四档筛选<strong>全部在客户端做</strong>：<code>GET /api/alerts</code>
          是泛型 list，<strong>没有筛选参数</strong> ——
          <code>?level=red</code> 会被 FastAPI <strong>静默忽略</strong>（不报错、只返回全量），
          这是计划约束第 9 条那一档。⚠️ 而「我任教的班」与「教学班」两档还要再绕一层：
          实测演示库的 32 行预警<strong>全是学生级</strong>（<code>course_section_id</code> 为
          <code>null</code>），故班级归属是按 <code>enrollment</code> 名册<strong>反查</strong>出来的
          （⚠️ 演示库上每个学生恰好 2 个班：行政班 + 分层班，故一条学生级预警会同时
          归属两个班）。
          <br />⚠️⚠️ 而「归属 → 班级级」那一档在演示库上<strong>仍然为空</strong>，
          但理由<strong>只有一个</strong>，且它就是上面那一条「规则没命中」。
          <br />⚠️ 而<strong>「就算触发了教师也读不到」不是理由</strong>：
          后端给「一行没有学生所有者的预警」（那一档的行 <code>student_id IS NULL</code>，
          按学生键收窄本来对任何教师都不可见）补了<strong>第二根轴</strong> ——
          <strong>该班的任课教师读得到它</strong>（别的班的教师与不带任何班的教师仍然 403，
          学生也仍然读不到，管理员全读）。⚠️ 于是这一档空的原因<strong>只有一个</strong>：
          「演示库没有班级级预警」，不是「教师读不到」。
          第二根轴的判据与它那一条失效方向的逐字取证见 spec §13.4.8。
        </p>
      </section>

      <!-- 02 · 队列 -->
      <section class="t-card">
        <SectionHead :index="2" level="red" label="QUEUE" />
        <div class="t-subhead">
          <span class="t-subhead__title">
            {{ sorted.length }} 条（筛自 {{ totals.total }} 条）
          </span>
          <span class="t-subhead__aside">红 → 黄 → 绿，再按触发时刻降序</span>
        </div>

        <!-- ⚠️ 空态**分两种**：一条都没有 vs 这一档筛选恒为空 -->
        <div v-if="totals.total === 0" class="t-empty">
          <svg class="t-empty__mark" viewBox="0 0 88 20" aria-hidden="true">
            <path class="t-empty__mark-line" d="M2 6 H86" />
            <path class="t-empty__mark-hair" d="M2 14 H40" />
          </svg>
          <p class="t-empty__title zh-title">我这个范围里一条预警都没有</p>
          <p class="t-empty__note">
            一条预警都没有。⚠️ 预警是<strong>批处理产物</strong>
            （<code>alert_stage.evaluate_alerts</code>），故这一档意味着
            「还没跑过每日批处理」、「跑过但一条规则都没命中」，
            或（第三种，它来自「按任教范围收窄」那一条口径）
            「<strong>我任教的班里</strong>一条都没有，而别的班有」——
            那一档管理员登录才看得见。
          </p>
        </div>

        <div v-else-if="sorted.length === 0" class="t-empty">
          <svg class="t-empty__mark" viewBox="0 0 88 20" aria-hidden="true">
            <path class="t-empty__mark-line" d="M2 6 H86" />
            <path class="t-empty__mark-hair" d="M2 14 H40" />
          </svg>
          <p class="t-empty__title zh-title">
            这一档筛选下没有预警
            <template v-if="scopeFilter === 'section'">（班级级）</template>
          </p>
          <p v-if="scopeFilter === 'section'" class="t-empty__note">
            ⚠️ <strong>这不是坏了</strong>：演示库的 32 行预警 <code>course_section_id</code>
            全是 <code>null</code>（全学生级），而<strong>班级级</strong>的规则只有一条 ——
            <code>YELLOW_CLASS_RPE_HIGH</code>（课堂 RPE 均值 &gt; 7）。
            实测演示库上 5 个班的均值最高是 <strong>6.93</strong>，
            <strong>差 0.07 没有越线</strong> → 一行都没触发。
            <!-- ⚠️ Plan 06 Task 8b：本段此前还写着**第二个**理由（「就算触发了教师也读不到，
                 因为 staff_taught 按学生键收窄、只有管理员读得到」），而那一格 Critical
                 本波已修 —— 今天该班的任课教师**读得到**自己班的班级级预警。
                 于是空态的理由**只剩一个**：演示库没有班级级预警。
                 ⚠️ 文案不许撒谎，故第二格删掉（同一件事在上面那段「为什么」里逐字记了一次，
                 本处不抄第二份）。⚠️ 而演示库上这一格**仍然为空**，故本段仍然渲染得到、
                 不是死代码。 -->
            <br />⚠️ 而<strong>它一旦触发</strong>，本页就显示得到：<code>GET /api/alerts</code>
            对「一行没有学生所有者的预警」按<strong>那个班是不是我
            本学期任教的</strong>判（spec §13.4.8），故我任教的班的班级级预警会出现在这一档里
            （别的班的不会）。
            <br />要看学生级的那些行，把「归属」切回<strong>全部</strong>或<strong>学生级</strong>。
          </p>
          <p v-else class="t-empty__note">
            换一个筛选档看看：等级
            <strong>{{ LEVEL_ZH[levelFilter] }}</strong> · 状态
            <strong>{{ STATUS_ZH[statusFilter] }}</strong> · 归属
            <strong>{{ SCOPE_ZH[scopeFilter] }}</strong> · 教学班
            <strong>{{ sectionFilter === 'all' ? '全部' : `#${sectionFilter}` }}</strong>。
          </p>
        </div>

        <ol v-else class="q">
          <li
            v-for="a in sorted"
            :key="a.id"
            class="q__row"
            :class="[`q__row--${levelOf(a.level)}`, a.status === 'pending' ? '' : 'q__row--done']"
          >
            <div class="q__head">
              <span class="pill" :class="`pill--${levelOf(a.level)}`">{{ alertLevelZh(a.level) }}</span>
              <span class="q__rule zh-title">{{ reasonZh(a.rule_id) }}</span>
              <span class="q__ruleid data">{{ a.rule_id }}</span>
              <span class="pill q__status" :class="a.status === 'pending' ? 'pill--amber' : 'pill--green'">
                {{ alertStatusZh(a.status) }}
              </span>
            </div>

            <dl class="q__meta">
              <dt>对象</dt>
              <dd>
                <RouterLink v-if="a.student_id !== null" :to="`/t/students/${a.student_id}`">
                  {{ subjectOf(a) }} <span class="data">#{{ a.student_id }}</span>
                </RouterLink>
                <template v-else>{{ subjectOf(a) }}</template>
                <span class="q__why">
                  （{{ a.course_section_id === null ? '学生级' : '班级级' }} ·
                  <code>subject_key = {{ a.subject_key }}</code>）
                </span>
              </dd>
              <dt>归属的班</dt>
              <dd class="data">
                <template v-if="sectionsOfAlert(a).length === 0"><span class="unknown">{{ UNKNOWN }}</span></template>
                <template v-else>
                  {{ sectionsOfAlert(a).map((id) => `#${id} ${data?.sectionNameOf.get(id) ?? ''}`).join('、') }}
                </template>
              </dd>
              <dt>触发于</dt>
              <dd class="data">{{ stampOf(a.triggered_at) }}</dd>
              <dt>窗口键</dt>
              <dd class="data">
                {{ a.window_key }}
                <span class="q__why">
                  （去重靠 DB：<code>(rule_id, subject_key, semester_id, window_key)</code> 唯一，
                  故前端<strong>不需要</strong>自己去重 —— 约束第 18 条）
                </span>
              </dd>
              <dt>处置痕迹</dt>
              <dd class="data">
                <template v-if="a.handled_action === null && a.handled_at === null">
                  <span class="unknown">{{ UNKNOWN }}</span>（还没处置过）
                </template>
                <template v-else>
                  {{ actionZh(a.handled_action) }}
                  <template v-if="a.handled_at"> · {{ stampOf(a.handled_at) }}</template>
                  <template v-else>
                    <span class="q__why">
                      · ⚠️ <code>handled_at</code> 是空的：那一档是「记了一笔备注」，
                      <strong>status 仍是 pending</strong>（备注不是处置）
                    </span>
                  </template>
                </template>
              </dd>
              <dt>学期 / batch</dt>
              <dd class="data">semester #{{ a.semester_id }} · batch #{{ a.batch_id }}</dd>
            </dl>

            <!-- 三个动作（⚠️ 字面值与中文都从 present.ts 的 HANDLE_ACTION_OPTIONS 来） -->
            <div v-if="a.status === 'pending'" class="q__act">
              <div v-for="opt in HANDLE_ACTION_OPTIONS" :key="opt.value" class="q__actcell">
                <button
                  type="button"
                  class="btn"
                  :class="{ 'btn--primary': opt.tone === 'red' }"
                  :disabled="busyId !== null"
                  :title="opt.hint"
                  @click="submit(a, opt.value)"
                >
                  {{ busyId === a.id ? '正在…' : opt.zh }}
                </button>
                <span class="q__acthint">{{ opt.hint }}</span>
                <input
                  v-if="opt.needsNote"
                  class="input q__note"
                  type="text"
                  :value="noteOf(a.id)"
                  placeholder="备注（这一档必填，为空会 422 unprocessable_value）"
                  aria-label="备注"
                  @input="setNote(a.id, ($event.target as HTMLInputElement).value)"
                />
              </div>
            </div>
            <p v-else class="q__locked">
              ⚠️ 这一条的 <code>status</code> 是 <strong>{{ alertStatusZh(a.status) }}</strong>，
              故 <code>POST …/handle</code> 会回 <strong>409 <code>alert_not_pending</code></strong>
              —— 三个按钮因此<strong>不出现</strong>（不是禁用）：教师改主意的正确处置是
              等下一轮求值按 <code>window_key</code> 落一条新行，而不是把一条已经处置过的痕迹翻回去。
            </p>

            <!-- 处置结果 -->
            <div v-if="outcomes.get(a.id)" class="q__outcome">
              <template v-if="outcomes.get(a.id)?.ok">
                <p class="q__oktitle">
                  ✓ {{ actionZh(outcomes.get(a.id)?.action ?? '') }} 已提交 ·
                  status → <strong>{{ alertStatusZh(outcomes.get(a.id)?.status) }}</strong>
                </p>
                <p v-if="outcomes.get(a.id)?.adjustmentWritten === false" class="q__why">
                  ⚠️ <code>adjustment</code> 是 <code>null</code> —— <strong>这是有信息的一档，不是失败</strong>：
                  一处方一周<strong>至多一条</strong> <code>source='auto'</code> 的调整
                  （用户 2026-10-08 裁定），那一周已经减过量了，故本次<strong>未再减</strong>。
                  HTTP 仍是 200、<code>status</code> 仍变 <code>handled</code>；
                  教师这一次点击<strong>有效的部分</strong>是「我看过了、并且推了消息给学生」。
                </p>
                <p v-else-if="outcomes.get(a.id)?.adjustmentWritten === true" class="q__why">
                  ✓ 写了一条 <code>weekly_adjustment</code>（<code>source='auto'</code>、
                  <code>factor=0.8</code>）。
                </p>
                <p class="q__why">
                  站内消息：
                  <template v-if="outcomes.get(a.id)?.notificationSent">✓ 已推给学生</template>
                  <template v-else>
                    <span class="unknown">{{ UNKNOWN }}</span>（这一档动作不发消息）
                  </template>
                </p>

                <!-- ⚠️ 派单逐字要求：处置成功后**刷新训练单**（减量已生效） -->
                <div v-if="outcomes.get(a.id)?.sheet" class="q__sheet">
                  <p class="q__sheettitle caps">处置之后回读的训练单（教师侧端点）</p>
                  <p class="q__factor" :class="`q__factor--${factorToneOf(outcomes.get(a.id)?.sheet?.factor)}`">
                    {{ factorSentenceOf(outcomes.get(a.id)!.sheet!) }}
                  </p>
                  <p class="q__why">
                    微周期第 <strong class="num">{{ outcomes.get(a.id)?.sheet?.week }}</strong> 周 ·
                    系数 <strong class="num">{{ num(outcomes.get(a.id)?.sheet?.factor ?? null, 2) }}</strong> ·
                    reasons: <code>{{ (outcomes.get(a.id)?.sheet?.reasons ?? []).join(', ') || UNKNOWN }}</code> ·
                    sources: <code>{{ (outcomes.get(a.id)?.sheet?.sources ?? []).join(', ') || UNKNOWN }}</code>
                    <template v-if="(outcomes.get(a.id)?.sheet?.reasons ?? []).length > 1">
                      · ⚠️ <strong>{{ (outcomes.get(a.id)?.sheet?.reasons ?? []).length }} 条 reason
                      而系数只有一个 0.8</strong> —— 一处方一周至多一条 auto 调整，
                      这不是 bug（约束第 13 条）
                    </template>
                  </p>
                  <!-- ⚠️ 训练量按单位分列，**不跨单位求和** -->
                  <p class="q__why">
                    本周训练量（按单位分列）：
                    <template v-if="volumesOf(outcomes.get(a.id)!.sheet!).length === 0">
                      <span class="unknown">{{ UNKNOWN }}</span>（每个动作的 <code>volume_unit</code> 都是
                      <code>unspecified</code>，⚠️ 那不是 0 分钟）
                    </template>
                    <template v-else>
                      <span
                        v-for="v in volumesOf(outcomes.get(a.id)!.sheet!)"
                        :key="v.unit"
                        class="q__vol"
                      >
                        <strong class="num">{{ v.total.toFixed(1) }}</strong> {{ volumeUnitZh(v.unit) }}
                      </span>
                    </template>
                    <span class="q__why">
                      ⚠️ 刻意不加总：后端<strong>逐字禁止</strong>跨单位求和
                      （「48 分钟 + 120 次 = 168 什么？」），且有守卫按键集断言
                      （处方那一层的口径见 spec §7）。
                    </span>
                  </p>
                </div>
                <p v-else-if="outcomes.get(a.id)?.sheetError" class="q__why">
                  训练单回读：<code>{{ outcomes.get(a.id)?.sheetError?.code }}</code> ·
                  {{ outcomes.get(a.id)?.sheetError?.status }} ——
                  {{ outcomes.get(a.id)?.sheetError?.message }}
                  <span class="q__why">
                    ⚠️ 两档 404（<code>no_active_prescription</code> /
                    <code>outside_microcycle</code>）是常态，不是故障；
                    处置本身<strong>已经成功</strong>。
                  </span>
                </p>
              </template>

              <template v-else>
                <p class="q__badtitle">
                  ✗ {{ outcomes.get(a.id)?.error?.code }} ·
                  {{ outcomes.get(a.id)?.error?.status }}
                </p>
                <p class="q__why">
                  <template v-if="outcomes.get(a.id)?.error?.code === 'alert_not_pending'">
                    这一条已经处置过了（<code>status != 'pending'</code>）。⚠️ 这一档挡的正是
                    「减量 20%」被点两次：本周训练单是该周全部 factor 的<strong>累乘</strong>，
                    再点一次就是 0.8 × 0.8 = 0.64。
                  </template>
                  <template v-else-if="outcomes.get(a.id)?.error?.code === 'unprocessable_value'">
                    「记一笔备注」那一档的 <code>note</code> 不得为空白。
                  </template>
                  <template v-else-if="outcomes.get(a.id)?.error?.code === 'forbidden'">
                    当前身份不是一个在册教师（<code>require_teacher</code>）。
                  </template>
                </p>
                <p class="q__why"><code>{{ outcomes.get(a.id)?.error?.message }}</code></p>
              </template>
            </div>
          </li>
        </ol>
      </section>
    </template>
  </div>
</template>

<style scoped>
/* ⚠️ 外壳 / 卡片 / 空态 / 说明块在 `styles/teacher.css`；这里只写队列独有的东西。
   ⚠️ 一个色值都不写死。 */

/* ⚠️ Plan 06 Task 8 新加的那一行「范围」说明（模板里逐字写了它为什么必须在页面上）。
   ⚠️ 刻意**不进** `styles/teacher.css`：那一格是本页独有的
   （大屏与周报本来就按班取数，只有队列是「一张全校的表按人筛」）。 */
.t-head__scope {
  max-inline-size: 62ch;
  margin-block-start: var(--space-2);
  font-size: var(--fs-micro);
  line-height: 1.5;
  color: var(--ink-faint);
}

.t-filters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
}

.t-filtergroup {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.t-filtergroup__label {
  color: var(--ink-soft);
}

.t-chip {
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-raise);
  font-family: var(--font-ui);
  font-size: var(--fs-small);
  color: var(--ink-soft);
}

.t-chip--on {
  border-color: var(--primary);
  background: var(--primary);
  color: var(--on-primary);
}

.t-select {
  min-width: 16em;
}

/* ---------------------------------------------------------------- 队列 */
.q {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.q__row {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-3) var(--space-3) var(--space-4);
  border: var(--border-hairline);
  border-radius: var(--radius);
  border-inline-start: var(--bar-accent) solid var(--border);
  background: var(--surface-raise);
}

/* 左端那条竖色带 = 分道线母题竖过来（与 `student.css` 的 `.s-todo__mark` 同一条） */
.q__row--red {
  border-inline-start-color: var(--red);
}
.q__row--amber {
  border-inline-start-color: var(--amber);
}
.q__row--green {
  border-inline-start-color: var(--green);
}

.q__row--done {
  background: var(--surface-sunken);
}

.q__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2);
}

.q__rule {
  font-size: var(--fs-body);
  font-weight: var(--fw-700);
}

.q__ruleid {
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.q__status {
  margin-inline-start: auto;
}

.q__meta {
  display: grid;
  grid-template-columns: 7em 1fr;
  gap: 2px var(--space-3);
  padding-block: var(--space-2);
  border-block: var(--border-hairline);
  font-size: var(--fs-small);
}

.q__meta dt {
  font-family: var(--font-ui);
  font-weight: var(--fw-600);
  letter-spacing: var(--tracking-caps);
  text-transform: uppercase;
  color: var(--ink-faint);
  white-space: nowrap;
}

.q__meta dd {
  margin: 0;
  color: var(--ink-soft);
  min-width: 0;
  overflow-wrap: anywhere;
}

.q__why {
  font-family: var(--font-ui);
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.q__act {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
}

.q__actcell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  align-items: flex-start;
}

.q__acthint {
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.q__note {
  width: 100%;
  font-size: var(--fs-small);
}

.q__locked {
  font-size: var(--fs-small);
  color: var(--ink-soft);
  padding: var(--space-2) var(--space-3);
  background: var(--surface-sunken);
  border-inline-start: var(--bar-hair) solid var(--border);
}

/* ------------------------------------------------------------ 处置结果 */
.q__outcome {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-3);
  background: var(--surface-sunken);
  border-inline-start: var(--bar-accent) solid var(--primary);
  font-size: var(--fs-small);
}

.q__oktitle {
  font-family: var(--font-ui);
  font-weight: var(--fw-600);
  letter-spacing: var(--tracking-caps);
  text-transform: uppercase;
  color: var(--green);
}

.q__badtitle {
  font-family: var(--font-ui);
  font-weight: var(--fw-600);
  letter-spacing: var(--tracking-caps);
  text-transform: uppercase;
  color: var(--red);
}

.q__sheet {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-block-start: var(--space-2);
  padding: var(--space-3);
  background: var(--surface-raise);
  border: var(--border-hairline);
}

.q__sheettitle {
  color: var(--ink-soft);
}

.q__factor {
  font-family: var(--font-ui);
  font-weight: var(--fw-700);
  font-size: var(--fs-subtitle);
}

.q__factor--red {
  color: var(--red);
}
.q__factor--green {
  color: var(--green);
}

.q__vol {
  margin-inline-end: var(--space-3);
}
</style>
