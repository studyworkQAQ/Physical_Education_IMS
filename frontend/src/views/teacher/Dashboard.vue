<script setup lang="ts">
/**
 * `views/teacher/Dashboard.vue` —— **教师大屏**（`/t/dashboard`）。本项目的展示 centerpiece。
 *
 * ---------------------------------------------------------------------------
 * 读的端点（⚠️ 全部实测过，出处见 task-3-report.md 第 3 节）
 * ---------------------------------------------------------------------------
 *  1. `GET /api/teachers?limit=200` · **匿名** —— 工号 → `teacher.id`（下一格要用）；
 *  2. `GET /api/course-sections?limit=200` · **匿名** —— 5 个教学班 + `teacher_id`，
 *     据此算出「**我**任教的班」；
 *  3. `GET /api/dashboard/class/{course_section_id}?as_of=` · ⚠️ **教师头** —— 整屏。
 *     实测它过 `require_teaches_section`：**不是自己任教的班 → 403 `forbidden`**
 *     （T0001 只能读班 1 与班 3；班 2/4/5 一律 403）。
 *  4. `GET /api/enrollments?limit=200` · **匿名** —— 名册（`course_section_id` → 学号集合）。
 *     ⚠️ 它是**承重**的：30 条预警**全是学生级**（`course_section_id` 为 `null`、
 *     `student_id` 非空），故「这个班的预警」只能按名册反查归属。
 *  5. `GET /api/alerts?limit=200` · **匿名** —— 预警行（客户端过滤，约束第 9 条）；
 *  6. `GET /api/students?limit=200` · **匿名** —— `student_id` → 姓名（榜上与名单上要显示人）；
 *  7. `GET /api/class-sessions?limit=200` · **匿名** —— 这个班的课次（口令那一格要挑一节）；
 *  8. `GET /api/class-sessions/{id}/rpe-token` · ⚠️ **教师头** —— **读**既有口令；
 *  9. `POST /api/class-sessions/{id}/open-rpe` · ⚠️ **教师头** —— **发起**课堂快评。
 *
 * ⚠️ 计划第 8 节自审第 5 条：**优先用 ⑧**（它是 GET，语义对）。⑨ 是 POST 且幂等
 * 不换口令，拿它当读操作使会让前端靠 `already_open` 反推「什么都没发生」。
 * 故本页的默认路径是 ⑧（每个班**只读一次**、结果缓存），⑨ 只在教师点按钮时发。
 * ⚠️ `rpe_opened` 为假时 ⑧ 是 **409 `rpe_not_opened`**（不是 404、不是 `null`，
 * 约束第 16 条）→ 本页把那一档渲染成「这一节课还没发起」+ 一个发起按钮。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ 三处「显示成什么」的口径（都是计划约束逐字要求的）
 * ---------------------------------------------------------------------------
 *  - **本周概览不是一个训练量数**：⚠️ 实测 `blocks` 的**七个键里根本没有训练量**
 *    （`layer_distribution` / `rpe_summary` / `checkin_rate_by_layer` /
 *    `progress_board` / `alert_summary` / `suggestion` / `abnormal_roster`），
 *    故大屏**结构上不可能**撞上「跨单位求和」那一档（`prescription_stage.py:411-417`
 *    逐字禁止：「48 分钟 + 120 次 = 168 什么？」）。本块放的是名册人数、周次、
 *    数据水位、人均 RPE 与后端算好的那一句 `suggestion`。
 *  - **`suggestion` 原样显示**（后端算好的一句话，前端不再判一次）。
 *  - **`null` 一律「—」**：`rpe_summary.mean`（那一周没有快评）、
 *    `checkin_rate_by_layer[层].rate`（那一层没人，实测 `insufficient_data` 恒为 `null`）、
 *    `abnormal_roster[i].peak_rpe`（可空）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 5 秒轮播与数字滚动会不会打架（派单点名的顶回候选 ④）
 * ---------------------------------------------------------------------------
 * 会，如果什么都不做：`StatBlock` 的 `rollTo` 从**当前显示值**滚到新值，于是切班时
 * 「行政班01 的 6.37」会**变形**成「提升班的 5.9」—— 读起来像同一个班的数字在抽搐。
 * 本页的三条处置：
 *  1. **`:key="sectionId"` 挂在被轮播的那棵子树上** → 切换是**重建**，
 *     `StatBlock` 从 0 滚到新值（一次干净的「计时牌归零再走」），不是变形；
 *  2. **`<Transition mode="out-in">` + 200ms** → 任何时刻只有一帧在场
 *     （`in-out` 会让两帧叠加，12 列网格里的两帧会挤成一片），
 *     而 200ms ≪ 5000ms 的停留，故「过渡没完就切下一帧」不可能发生；
 *  3. **`prefers-reduced-motion` 时根本不自动轮播**（只留手动的班次按钮）——
 *     自动前进的内容对前庭敏感的人是一次真实的伤害，而 `base.css` 的总开关
 *     只把动画时长压到 0.01ms、**压不掉「内容自己会变」**这件事，故这里自己判一次。
 *  ⚠️ 还有一条进度条（`.bs-progress`）：它回答「还有多久切下一个班」。
 *     一个没有进度指示的自动轮播会在教师讲到一半时把画面切走，
 *     那是投影场景里最恼人的一种失效。
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { ApiError } from '../../api/client'
import {
  getClassDashboard,
  listAlerts,
  listClassSessions,
  listCourseSections,
  listEnrollments,
  listStudents,
  listTeachers,
  openRpe,
  readRpeToken,
} from '../../api/endpoints'
import type { components } from '../../api/generated/schema'
import type { AlertListItem, ClassSessionListItem, CourseSectionListItem } from '../../api/types'
import LaneDivider from '../../components/LaneDivider.vue'
import StatBlock from '../../components/StatBlock.vue'
import TeacherNav from '../../components/TeacherNav.vue'
import CompletionBars, { type CompletionRow } from '../../components/charts/CompletionBars.vue'
import LayerDonut, { type LayerCounts } from '../../components/charts/LayerDonut.vue'
import ProgressBoard from '../../components/charts/ProgressBoard.vue'
import { useAsync } from '../../composables/useAsync'
import {
  LAYER_SLOTS,
  UNKNOWN,
  abnormalReasonZh,
  alertLevelZh,
  groupingModeZh,
  levelOf,
  num,
  reasonZh,
  rpeAnchorOf,
  rpeToneOf,
  shortDate,
  weekdayOf,
} from '../../present'
import { useIdentityStore } from '../../stores/identity'

type Screen = components['schemas']['ClassDashboardRead']
type CourseSection = CourseSectionListItem

/** 轮播的停留时长。⚠️ 派单逐字要求 5 秒；`teacher.css` 的进度条读同一个值
 *  （通过 `--bs-dwell` 传下去），故「进度条走完」与「真的切了」不可能漂。 */
const DWELL_MS = 5000

const identity = useIdentityStore()

/* ==========================================================================
   一次读取：全部匿名端点 + 我任教的每个班的大屏
   ========================================================================== */

interface SectionFrame {
  section: CourseSection
  /** 读成功的那一屏；失败时是 `null`（失败原因在 `error`）。 */
  screen: Screen | null
  error: ApiError | null
  /** 名册（学号集合）。⚠️ 预警的班级归属靠它反查。 */
  roster: Set<number>
}

interface Loaded {
  frames: SectionFrame[]
  alerts: AlertListItem[]
  nameOf: Map<number, string>
  sessions: ClassSessionListItem[]
  meStaffNo: string | null
  meName: string | null
}

const { data, loading, settled, reload } = useAsync<Loaded | null>(async () => {
  const staffNo = identity.teacherStaffNo
  if (staffNo === null) return null

  // ⚠️ 6 个匿名读**并发**：它们互不依赖，而大屏是一次冷启动就要满屏的场景。
  const [teachers, sections, enrollments, alerts, students, sessions] = await Promise.all([
    listTeachers({ limit: 200 }),
    listCourseSections({ limit: 200 }),
    listEnrollments({ limit: 200 }),
    listAlerts({ limit: 200 }),
    listStudents({ limit: 200 }),
    listClassSessions({ limit: 200 }),
  ])

  const me = teachers.items.find((t) => t.staff_no === staffNo) ?? null
  const rosterBy = new Map<number, Set<number>>()
  for (const row of enrollments.items) {
    const set = rosterBy.get(row.course_section_id) ?? new Set<number>()
    set.add(row.student_id)
    rosterBy.set(row.course_section_id, set)
  }

  // ⚠️⚠️ **只轮播我任教的班**：`GET /api/dashboard/class/{id}` 过
  //    `require_teaches_section`，实测 T0001 读班 2/4/5 一律 **403 `forbidden`**。
  //    轮播全部 5 个班的话，5 帧里有 3 帧是一块错误 —— 那不是大屏，那是故障展示。
  const mine = sections.items.filter((s) => me !== null && s.teacher_id === me.id)

  const frames = await Promise.all(
    mine.map(async (section): Promise<SectionFrame> => {
      let screen: Screen | null = null
      let error: ApiError | null = null
      try {
        screen = await getClassDashboard(section.id, { asOf: identity.asOf })
      } catch (err) {
        // ⚠️ 一个班读不到**不该**让整屏失败：轮播跳过它、并把原因写在那一帧上。
        error = err instanceof ApiError ? err : null
        if (!(err instanceof ApiError)) console.error('[dashboard]', err)
      }
      return { section, screen, error, roster: rosterBy.get(section.id) ?? new Set<number>() }
    }),
  )

  return {
    frames,
    alerts: alerts.items,
    nameOf: new Map(students.items.map((s) => [s.id, s.name])),
    sessions: sessions.items,
    meStaffNo: staffNo,
    meName: me?.name ?? null,
  }
})

// ⚠️ 换身份或换业务日都要重读：`as_of` 是查询参数，不是渲染期的过滤条件。
watch([() => identity.teacherStaffNo, () => identity.asOf], () => void reload())

const frames = computed<SectionFrame[]>(() => data.value?.frames ?? [])
const nameOf = computed(() => data.value?.nameOf ?? new Map<number, string>())

function nameOfStudent(id: number): string | null {
  return nameOf.value.get(id) ?? null
}

/* ==========================================================================
   轮播（5 秒 / 只在我任教的班之间 / reduced-motion 时不自动）
   ========================================================================== */

const activeIndex = ref(0)
const paused = ref(false)
let timer: number | null = null

/** ⚠️ 自动前进的那一档要尊重 `prefers-reduced-motion`（理由见文件头第 3 条）。 */
const reducedMotion = ref(false)
if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
  reducedMotion.value = window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

const autoPlay = computed(
  () => frames.value.length > 1 && !paused.value && !reducedMotion.value,
)

function stopTimer(): void {
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
}

function startTimer(): void {
  stopTimer()
  if (!autoPlay.value) return
  timer = window.setInterval(() => {
    const n = frames.value.length
    if (n > 1) activeIndex.value = (activeIndex.value + 1) % n
  }, DWELL_MS)
}

watch(autoPlay, () => startTimer())
watch(
  () => frames.value.length,
  () => {
    if (activeIndex.value >= frames.value.length) activeIndex.value = 0
    startTimer()
  },
)
onBeforeUnmount(stopTimer)
// ⚠️ `useAsync` 是异步的：首帧时 `frames` 还是空的，故数据到了之后要再起一次计时器。
watch(
  () => data.value !== null,
  (ready) => {
    if (ready) startTimer()
  },
)

/** 手动挑一个班（点班次按钮）。⚠️ 顺手**重置**计时器：否则点完 1 秒后就又被切走。 */
function pick(index: number): void {
  activeIndex.value = index
  startTimer()
}

const active = computed<SectionFrame | null>(() => frames.value[activeIndex.value] ?? null)
const screen = computed<Screen | null>(() => active.value?.screen ?? null)
const blocks = computed(() => screen.value?.blocks ?? null)

/* ==========================================================================
   预警：按名册反查归属（30 行全是学生级）
   ========================================================================== */

const myAlerts = computed<AlertListItem[]>(() => {
  const frame = active.value
  if (!frame) return []
  return (data.value?.alerts ?? []).filter(
    (a) => a.student_id !== null && frame.roster.has(a.student_id),
  )
})

const LEVEL_ORDER = ['red', 'yellow', 'green'] as const

/** 待处理的那一批，按 level（红→黄→绿）再按触发时刻排。
 *  ⚠️ 排序住在**页面**、不住在组件里（`endpoints.ts` 的三个收集助手同一条口径：
 *  「列表的顺序」是展示层的事）。 */
const pendingAlerts = computed<AlertListItem[]>(() =>
  [...myAlerts.value]
    .filter((a) => a.status === 'pending')
    .sort(
      (a, b) =>
        LEVEL_ORDER.indexOf(a.level as (typeof LEVEL_ORDER)[number]) -
          LEVEL_ORDER.indexOf(b.level as (typeof LEVEL_ORDER)[number]) ||
        b.triggered_at.localeCompare(a.triggered_at),
    ),
)

/** 大屏上只列前 6 条（一屏放不下 15 条，而「去预警队列」那一格才是处置的地方）。 */
const alertPreview = computed(() => pendingAlerts.value.slice(0, 6))

/** 后端 `alert_summary` 的三档 pending。⚠️ 它是**权威**的那一份（与班级周报同源，
 *  守卫是后端 `test_the_dashboard_and_the_stored_report_agree_on_the_same_sunday`）。 */
function summaryPending(level: string): number | null {
  const cell = blocks.value?.alert_summary?.[level]
  if (!cell) return null
  const pending = cell.pending
  return typeof pending === 'number' ? pending : null
}

/** 对拍：按名册反查出来的三档条数（⚠️ 实测 5 个班**逐个**与后端 `alert_summary`
 *  的 `pending` 相等）。把它显示出来是**有意的**：它让「前端自己算的归属」这件事
 *  可被教师当场核对，而不是藏在一个 filter 里。 */
const crossCheck = computed(() => {
  const counted = { red: 0, yellow: 0, green: 0 }
  for (const a of pendingAlerts.value) {
    if (a.level in counted) counted[a.level as keyof typeof counted] += 1
  }
  const backend = {
    red: summaryPending('red'),
    yellow: summaryPending('yellow'),
    green: summaryPending('green'),
  }
  const agree =
    backend.red === counted.red && backend.yellow === counted.yellow && backend.green === counted.green
  return { counted, backend, agree }
})

/* ==========================================================================
   分层 / 完成率 / 进步榜（三个图表组件的输入）
   ========================================================================== */

const layerCounts = computed<LayerCounts>(() => {
  const by = blocks.value?.layer_distribution?.by_layer ?? {}
  return {
    red: by.red ?? 0,
    yellow: by.yellow ?? 0,
    green: by.green ?? 0,
    insufficient_data: by.insufficient_data ?? 0,
  }
})

const completionRows = computed<CompletionRow[]>(() => {
  const by = blocks.value?.checkin_rate_by_layer ?? {}
  return LAYER_SLOTS.map((slot) => {
    const cell = by[slot.key]
    return {
      key: slot.key,
      zh: slot.zh,
      level: slot.level,
      students: cell?.students ?? 0,
      measured: cell?.measured ?? 0,
      rate: cell?.rate ?? null,
    }
  })
})

const layerFlow = computed(() => blocks.value?.layer_distribution?.flow ?? null)

/* ==========================================================================
   口令投屏
   ========================================================================== */

/** 这个班的课次，按「日期降序 + 节次降序」（最新的一节在最前）。 */
const sectionSessions = computed<ClassSessionListItem[]>(() => {
  const frame = active.value
  if (!frame) return []
  return (data.value?.sessions ?? [])
    .filter((s) => s.course_section_id === frame.section.id)
    .sort(
      (a, b) => b.session_date.localeCompare(a.session_date) || b.period - a.period,
    )
})

const pickedSessionId = ref<number | null>(null)

/** 换班时把「选中哪一节课」重置成这个班最新的那一节。 */
watch(
  () => active.value?.section.id ?? null,
  () => {
    pickedSessionId.value = sectionSessions.value[0]?.id ?? null
    token.value = null
    tokenError.value = null
    void readToken()
  },
  { immediate: true },
)

interface TokenState {
  classSessionId: number
  token: string
  /** `open-rpe` 的幂等标志：为真说明这一节课**早就发起过**、口令没换。 */
  alreadyOpen: boolean
}

const token = ref<TokenState | null>(null)
const tokenError = ref<ApiError | null>(null)
const tokenBusy = ref(false)

const pickedSession = computed(
  () => sectionSessions.value.find((s) => s.id === pickedSessionId.value) ?? null,
)

/** 读既有口令（`GET …/rpe-token`）。⚠️ 409 `rpe_not_opened` 是**内容**、不是错误横幅。 */
async function readToken(): Promise<void> {
  const id = pickedSessionId.value
  if (id === null) return
  tokenBusy.value = true
  tokenError.value = null
  try {
    const got = await readRpeToken(id)
    token.value = { classSessionId: got.class_session_id, token: got.rpe_token, alreadyOpen: false }
  } catch (err) {
    token.value = null
    tokenError.value = err instanceof ApiError ? err : null
    if (!(err instanceof ApiError)) console.error('[rpe-token]', err)
  } finally {
    tokenBusy.value = false
  }
}

/** 发起课堂快评（`POST …/open-rpe`）。⚠️ **幂等且不换口令**。 */
async function openNow(): Promise<void> {
  const id = pickedSessionId.value
  if (id === null || tokenBusy.value) return
  tokenBusy.value = true
  tokenError.value = null
  try {
    const got = await openRpe(id)
    token.value = {
      classSessionId: got.class_session_id,
      token: got.rpe_token,
      alreadyOpen: got.already_open,
    }
  } catch (err) {
    tokenError.value = err instanceof ApiError ? err : null
    if (!(err instanceof ApiError)) console.error('[open-rpe]', err)
  } finally {
    tokenBusy.value = false
  }
}

watch(pickedSessionId, () => {
  token.value = null
  tokenError.value = null
  void readToken()
})

/* ==========================================================================
   顶栏
   ========================================================================== */

const rpeSummary = computed(() => blocks.value?.rpe_summary ?? null)

/** 人均 RPE 的语义色（阈值取自后端两条规则，所有者是 `present.ts` 的 `rpeToneOf`）。
 *  ⚠️ 抽成一个 computed 而不是在模板里写三元：模板里那一格被用了两次
 *  （分道线的 `level` 与 `StatBlock` 的 `level`），写两遍就是两个所有者。 */
const rpeLevel = computed<'default' | 'red' | 'amber'>(() =>
  rpeToneOf(rpeSummary.value?.mean ?? null) === 'red' ? 'red' : rpeToneOf(rpeSummary.value?.mean ?? null) === 'amber' ? 'amber' : 'default',
)

/** 人均 RPE 的环比。⚠️ `delta` 可空；`previous_mean` 也可空。 */
const deltaText = computed(() => {
  const s = rpeSummary.value
  if (!s || s.delta === null) return UNKNOWN
  const sign = s.delta > 0 ? '+' : ''
  return `${sign}${s.delta.toFixed(2)}`
})

/** 7 天的曲线（`curve` 恒为 7 格，没有快评的那一格是 `null`）。 */
const curveCells = computed(() => {
  const curve = rpeSummary.value?.curve ?? []
  return curve.map((point, i) => ({
    index: i,
    day: point?.day ?? null,
    mean: point?.mean ?? null,
    submissions: point?.submissions ?? null,
  }))
})

const thresholds = computed(() => screen.value?.rpe_threshold_lines ?? null)
const screenThresholds = computed(() => screen.value?.screen_thresholds ?? null)
</script>

<template>
  <div class="bs-page">
    <TeacherNav />

    <!-- ⚠️ 没有教师身份 → 不假装在加载。大屏的**每一个**主端点都要教师头。 -->
    <div v-if="identity.teacherStaffNo === null" class="bs-empty">
      <svg class="bs-empty__mark" viewBox="0 0 88 20" aria-hidden="true">
        <path class="bs-empty__mark-line" d="M2 6 H86" />
        <path class="bs-empty__mark-hair" d="M2 14 H86" />
      </svg>
      <p class="bs-empty__title zh-title">还不知道你是哪位老师</p>
      <p>
        大屏的主端点 <code>GET /api/dashboard/class/{id}</code> 挂
        <strong><code>X-Teacher-Staff-No</code></strong>，而且它过
        <code>require_teaches_section</code> —— 不是自己任教的班一律
        <strong>403 <code>forbidden</code></strong>。故本页要先知道「你是谁」，
        才能算出「轮播哪几个班」。
      </p>
      <p>
        请在上面的身份切换器里选一位教师，或在 URL 上加
        <code>?teacher=T0001</code>。演示库有三位：
        <code>T0001</code> 陈国华（班 1 行政班01 + 班 3 提升班）、
        <code>T0002</code> 林慧敏（班 2 + 班 4）、
        <code>T0003</code> 赵志刚（班 5 拓展班）。
      </p>
    </div>

    <div v-else-if="loading && !settled" class="t-loading">
      <span class="t-loading__rule" aria-hidden="true"></span>
      <span>正在读整屏…</span>
    </div>

    <div v-else-if="frames.length === 0" class="bs-empty">
      <p class="bs-empty__title zh-title">这位老师名下没有教学班</p>
      <p>
        <code>GET /api/course-sections</code> 里 <code>teacher_id</code> 等于
        {{ data?.meName ?? '这位老师' }} 的行是 <strong class="num">0</strong> 条。
        ⚠️ 这不是「大屏坏了」：任教关系的判据是
        <code>course_section.teacher_id</code>（后端 <code>require_teaches_section</code>
        读的就是它），一个没有被指派任何班的工号就是这一档。
      </p>
    </div>

    <template v-else>
      <!-- ---------------------------------------------------------- 顶栏 -->
      <header class="bs-head">
        <div>
          <p class="caps bs-head__kicker">
            WEEK {{ num(screen?.week ?? null) }} · {{ identity.asOf }}
            {{ weekdayOf(identity.asOf) }} · 数据水位
            {{ screen?.watermark ?? UNKNOWN }}
          </p>
          <h2 class="zh-title bs-head__title">
            {{ screen?.course_section_name ?? active?.section.name ?? UNKNOWN }}
          </h2>
          <p class="bs-head__meta">
            学期 {{ screen?.semester_name ?? UNKNOWN }} ·
            {{ groupingModeZh(active?.section.grouping_mode) }} ·
            名册 <strong class="num">{{ num(screen?.roster_size ?? null) }}</strong> 人 ·
            本周从 {{ screen?.week_start ?? UNKNOWN }} 起 ·
            任课 {{ data?.meStaffNo ?? UNKNOWN }}
            <template v-if="data?.meName">（{{ data.meName }}）</template>
          </p>
        </div>

        <div class="bs-head__side">
          <div class="bs-dots" role="tablist" aria-label="轮播哪几个教学班">
            <button
              v-for="(frame, i) in frames"
              :key="frame.section.id"
              type="button"
              class="bs-dot"
              :class="{ 'bs-dot--on': i === activeIndex }"
              role="tab"
              :aria-selected="i === activeIndex"
              @click="pick(i)"
            >
              {{ i + 1 }} · {{ frame.section.name }}
            </button>
          </div>
          <p class="bs-fine">
            只轮播<strong>我任教的</strong> {{ frames.length }} 个班（读别的班会 403）·
            <template v-if="reducedMotion">
              检测到「减少动态效果」→ <strong>已停用自动轮播</strong>，请手动点上面的班次
            </template>
            <template v-else-if="frames.length === 1">只有一个班，无需轮播</template>
            <template v-else>
              每 {{ DWELL_MS / 1000 }} 秒自动切下一个
              <button type="button" class="bs-dot" @click="paused = !paused">
                {{ paused ? '继续轮播' : '暂停轮播' }}
              </button>
            </template>
          </p>
          <!-- ⚠️ 进度条与轮播同源（都读 DWELL_MS，通过 --bs-dwell 传给 CSS） -->
          <div
            v-if="autoPlay"
            class="bs-progress"
            :style="{ '--bs-dwell': `${DWELL_MS}ms` }"
            aria-hidden="true"
          >
            <span :key="activeIndex" class="bs-progress__bar"></span>
          </div>
        </div>
      </header>

      <!-- -------------------------------------------------- 被轮播的那一棵子树
           ⚠️ `:key` 是承重的：它让切班变成**重建**而不是**变形**（见文件头那段）。 -->
      <Transition name="bs-swap" mode="out-in">
        <div :key="active?.section.id ?? 'none'" class="bs-grid">
          <!-- 01 · 预警队列（跨 5 列 —— 计划第 2 节定的不对称网格） -->
          <section class="bs-panel bs-grid__alerts">
            <LaneDivider :index="1" tone="ink" level="red" label="ALERTS" />
            <div class="t-subhead">
              <span class="bs-panel__title">预警队列</span>
              <span class="bs-panel__aside">
                待处理 {{ pendingAlerts.length }} / 本班共 {{ myAlerts.length }} 条
              </span>
            </div>

            <div v-if="!screen" class="bs-empty">
              <p class="bs-empty__title zh-title">这一屏读不到</p>
              <p>
                <code>{{ active?.error?.code ?? 'error' }}</code> ·
                {{ active?.error?.status ?? UNKNOWN }} ——
                {{ active?.error?.message ?? '后端没有给理由。' }}
              </p>
            </div>

            <template v-else>
              <div class="bs-metrics">
                <StatBlock
                  v-for="lv in LEVEL_ORDER"
                  :key="lv"
                  :value="summaryPending(lv)"
                  :label="alertLevelZh(lv)"
                  unit="条待处理"
                  size="body"
                  tone="ink"
                  :level="levelOf(lv)"
                />
              </div>

              <div v-if="alertPreview.length === 0" class="bs-empty">
                <p class="bs-empty__title zh-title">本班没有待处理的预警</p>
                <p>
                  ⚠️ 30 条预警<strong>全是学生级</strong>（<code>course_section_id</code> 为
                  <code>null</code>），故「本班的」是按名册反查出来的
                  （本班名册 {{ active?.roster.size ?? 0 }} 人）。
                </p>
              </div>

              <ol v-else class="bs-list">
                <li v-for="a in alertPreview" :key="a.id" class="bs-alert">
                  <span class="pill" :class="`pill--${levelOf(a.level)}`">{{ alertLevelZh(a.level) }}</span>
                  <RouterLink class="bs-alert__who" :to="`/t/students/${a.student_id}`">
                    {{ nameOfStudent(a.student_id ?? 0) ?? `学生 #${a.student_id}` }}
                    <span class="bs-alert__id num">#{{ a.student_id }}</span>
                  </RouterLink>
                  <span class="bs-alert__rule">{{ reasonZh(a.rule_id) }}</span>
                </li>
              </ol>

              <p class="bs-fine">
                ⚠️ 只列前 {{ alertPreview.length }} 条（按 红 → 黄 → 绿、再按触发时刻）。
                对拍：按名册反查
                <strong class="num">{{ crossCheck.counted.red }}/{{ crossCheck.counted.yellow }}/{{ crossCheck.counted.green }}</strong>
                vs 后端 <code>alert_summary.pending</code>
                <strong class="num">{{ crossCheck.backend.red ?? '—' }}/{{ crossCheck.backend.yellow ?? '—' }}/{{ crossCheck.backend.green ?? '—' }}</strong>
                →
                <strong :class="crossCheck.agree ? 'bs-ok' : 'bs-bad'">
                  {{ crossCheck.agree ? '一致' : '不一致（本班名册或预警的窗口与后端不同）' }}
                </strong>
              </p>
              <RouterLink class="bs-btn bs-btn--track" to="/t/alerts">去预警队列处置 →</RouterLink>
            </template>
          </section>

          <!-- 02 · 分层分布（跨 4 列） -->
          <section class="bs-panel bs-grid__layers">
            <LaneDivider :index="2" tone="ink" label="LAYERS" />
            <div class="t-subhead">
              <span class="bs-panel__title">分层分布</span>
              <span class="bs-panel__aside">名册 {{ num(screen?.roster_size ?? null) }} 人</span>
            </div>
            <LayerDonut
              v-if="blocks"
              :counts="layerCounts"
              tone="ink"
              :caption="`算于 ${screen?.as_of ?? UNKNOWN}（现算，不读存下来的那一行）`"
            />
            <p v-if="layerFlow && !layerFlow.has_previous" class="bs-fine">
              周环比：<strong>暂无环比数据</strong> —— <code>flow.has_previous</code> 为
              <code>false</code>（这一周是学期里第一个有分层的周，没有上一周可比）。
              ⚠️ 它与「本周无人流动」在形状上完全相同（四个名单都空），
              故后端给了这一格开关；本页不猜。
            </p>
          </section>

          <!-- 03 · 本周概览（跨 3 列） -->
          <section class="bs-panel bs-grid__overview">
            <LaneDivider :index="3" tone="ink" label="THIS WEEK" />
            <span class="bs-panel__title">本周概览</span>
            <StatBlock
              :value="screen?.roster_size ?? null"
              label="名册人数"
              unit="人"
              tone="ink"
              size="display"
            />
            <StatBlock
              :value="rpeSummary?.mean ?? null"
              :decimals="2"
              label="人均课堂 RPE"
              tone="ink"
              size="display"
              :level="rpeToneOf(rpeSummary?.mean ?? null)"
              :caption="
                rpeSummary?.mean === null || rpeSummary?.mean === undefined
                  ? '这一周没有课堂快评（不是 0 分）'
                  : `量表 0–10 · 落在「${rpeAnchorOf(rpeSummary.mean)}」那一档 · 环比 ${deltaText}`
              "
            />
            <div class="bs-rows">
              <div class="bs-row">
                <span class="bs-row__key">学期周次</span>
                <span class="bs-row__val">第 {{ num(screen?.week ?? null) }} 周</span>
              </div>
              <div class="bs-row">
                <span class="bs-row__key">预警阈值线</span>
                <span class="bs-row__val">
                  班均 &gt; {{ num(thresholds?.class_mean_max ?? null, 1) }} ·
                  连续 ≥ {{ num(thresholds?.sustained_min ?? null, 1) }}
                </span>
              </div>
              <div class="bs-row">
                <span class="bs-row__key">算法建议</span>
                <!-- ⚠️ `suggestion` 是后端算好的一句话，**原样显示**、前端不再判一次 -->
                <span class="bs-row__val">{{ blocks?.suggestion ?? UNKNOWN }}</span>
              </div>
            </div>
            <p class="bs-fine">
              ⚠️ 本块<strong>没有</strong>「本周训练量」：整屏响应体的七个键里根本没有
              训练量那一格，故大屏结构上不可能把分钟与次数加在一起
              （后端 <code>prescription_stage.py</code> 逐字禁止跨单位求和，且有守卫按键集断言）。
            </p>
          </section>

          <!-- 04 · 课堂 RPE 的 7 天（跨 8 列） -->
          <section class="bs-panel bs-grid__rpe">
            <LaneDivider :index="4" tone="ink" :level="rpeLevel" label="RPE" />
            <div class="t-subhead">
              <span class="bs-panel__title">课堂快评的 7 天</span>
              <span class="bs-panel__aside">
                上周均值 {{ num(rpeSummary?.previous_mean ?? null, 2) }}
              </span>
            </div>
            <div class="bs-days">
              <div
                v-for="cell in curveCells"
                :key="cell.index"
                class="bs-day"
                :class="{ 'bs-day--on': cell.mean !== null }"
              >
                <span class="bs-day__d caps">{{ cell.day ? shortDate(cell.day) : `第 ${cell.index + 1} 天` }}</span>
                <!-- ⚠️ `null` → 「—」，不是 0：0 在这套量表上是「毫无感觉」，是一次真实作答 -->
                <span class="bs-day__v num">{{ num(cell.mean ?? null, 1) }}</span>
                <span class="bs-day__n">{{
                  cell.submissions === null ? '无快评' : `${cell.submissions} 份`
                }}</span>
              </div>
            </div>
            <p class="bs-fine">
              ⚠️ <code>curve</code> 恒为 <strong class="num">7</strong> 格，没有快评的那一天是
              <code>null</code>（本页渲染成「—」+「无快评」）。
              大屏的异常名单用的是<strong>另一套</strong>阈值：
              <code>screen_thresholds</code> = 连续
              {{ num(screenThresholds?.gap_days ?? null) }} 天未打卡 / RPE &gt;
              {{ num(screenThresholds?.rpe_max ?? null) }}，
              ⚠️ 与上面那两条<strong>预警</strong>判据线（7 / 9）是两套并存的东西，不得混用。
            </p>
          </section>

          <!-- 05 · 三层完成率（跨 4 列） -->
          <section class="bs-panel bs-grid__checkin">
            <LaneDivider :index="5" tone="ink" level="moss" label="CHECK-IN" />
            <div class="t-subhead">
              <span class="bs-panel__title">三层完成率</span>
              <span class="bs-panel__aside">本周（水位 {{ screen?.watermark ?? UNKNOWN }}）</span>
            </div>
            <CompletionBars
              v-if="blocks"
              :rows="completionRows"
              tone="ink"
              caption="分母 = 该层的处方训练日 × 人数；补卡、迟交（22:00 后）与休息日打卡都不计入。"
            />
          </section>

          <!-- 06 · 口令投屏（跨 4 列） -->
          <section class="bs-panel bs-grid__token">
            <LaneDivider :index="6" tone="ink" label="RPE TOKEN" />
            <span class="bs-panel__title">发起课堂快评</span>

            <div v-if="sectionSessions.length === 0" class="bs-empty">
              <p class="bs-empty__title zh-title">这个班还没有课次</p>
              <p>
                <code>class_session</code> 表里没有
                <code>course_section_id = {{ active?.section.id }}</code> 的行。
                ⚠️ 演示库的 8 节课只排给了班 1 与班 2（各 4 节），故班 3/4/5 就是这一档。
                建一节课走 <code>POST /api/class-sessions</code>（教师头）。
              </p>
            </div>

            <template v-else>
              <label class="bs-field">
                <span class="caps">哪一节课</span>
                <select v-model="pickedSessionId" class="bs-select">
                  <option v-for="s in sectionSessions" :key="s.id" :value="s.id">
                    课次 #{{ s.id }} · {{ s.session_date }}（{{ weekdayOf(s.session_date) }}）第
                    {{ s.period }} 节 · {{ s.rpe_opened ? '已发起' : '未发起' }}
                  </option>
                </select>
              </label>

              <!-- ⚠️ 极大字号投屏：学生是**手输**口令的（约束第 15 条），
                   故这一格要能在教室最后一排被抄下来。 -->
              <div v-if="token" class="bs-token">
                <span class="bs-token__label">课堂口令 · 请手输</span>
                <span class="bs-token__value">{{ token.token }}</span>
                <span class="bs-token__note">
                  课次 #{{ token.classSessionId }}
                  <template v-if="pickedSession">
                    · {{ pickedSession.session_date }} 第 {{ pickedSession.period }} 节
                  </template>
                  · 学生在 <code>/s/rpe</code> 手输这一串
                </span>
              </div>

              <div v-else-if="tokenError" class="bs-unknown">
                <p class="bs-unknown__title zh-title">
                  <template v-if="tokenError.code === 'rpe_not_opened'">这一节课还没发起快评</template>
                  <template v-else>口令读不到</template>
                </p>
                <p>
                  <code>{{ tokenError.code }}</code> · {{ tokenError.status }}
                  <template v-if="tokenError.code === 'rpe_not_opened'">
                    —— ⚠️ 这一档是 <strong>409</strong>，不是 404、也不是
                    <code>null</code>（约束第 16 条）。点下面那个按钮发起。
                  </template>
                </p>
                <p>{{ tokenError.message }}</p>
              </div>

              <div class="t-actions">
                <button type="button" class="bs-btn bs-btn--track" :disabled="tokenBusy" @click="openNow">
                  {{ tokenBusy ? '正在…' : '发起课堂快评' }}
                </button>
                <button type="button" class="bs-btn" :disabled="tokenBusy" @click="readToken">
                  读回既有口令
                </button>
              </div>
              <p class="bs-fine">
                ⚠️ <code>open-rpe</code> 是<strong>幂等</strong>的：已发起过就
                <code>already_open = true</code> 且<strong>不换口令</strong>
                （换掉的话第一个学生抄在纸上的那串会当场失效）。
                故「读」一律走 <code>GET …/rpe-token</code>，本页只在点按钮时才 POST。
                <template v-if="token?.alreadyOpen">
                  <strong>这一节课此前已经发起过，口令没有变。</strong>
                </template>
              </p>
            </template>
          </section>

          <!-- 07 · 异常名单（跨 8 列） -->
          <section class="bs-panel bs-grid__abnormal">
            <LaneDivider :index="7" tone="ink" level="amber" label="WATCH LIST" />
            <div class="t-subhead">
              <span class="bs-panel__title">异常名单</span>
              <span class="bs-panel__aside">
                {{ blocks?.abnormal_roster.length ?? 0 }} 人 ·
                阈值：连续 {{ num(screenThresholds?.gap_days ?? null) }} 天未打卡 / RPE &gt;
                {{ num(screenThresholds?.rpe_max ?? null) }}
              </span>
            </div>

            <div v-if="(blocks?.abnormal_roster.length ?? 0) === 0" class="bs-empty">
              <p class="bs-empty__title zh-title">本周没有人上榜</p>
              <p>
                没有学生同时满足「连续 {{ num(screenThresholds?.gap_days ?? null) }} 天未打卡」
                或「课堂 RPE 峰值 &gt; {{ num(screenThresholds?.rpe_max ?? null) }}」。
              </p>
            </div>

            <ol v-else class="bs-list">
              <li v-for="row in blocks?.abnormal_roster ?? []" :key="row.student_id" class="bs-alert">
                <RouterLink class="bs-alert__who" :to="`/t/students/${row.student_id}`">
                  {{ nameOfStudent(row.student_id) ?? `学生 #${row.student_id}` }}
                  <span class="bs-alert__id num">#{{ row.student_id }}</span>
                </RouterLink>
                <span class="bs-alert__rule">
                  {{ row.reasons.map(abnormalReasonZh).join(' · ') }}
                </span>
                <span class="bs-alert__nums num">
                  断卡 {{ row.gap_days }} 天 · 峰值 RPE
                  <!-- ⚠️ `peak_rpe` 可空 → 「—」，不是 0 -->
                  {{ row.peak_rpe === null ? UNKNOWN : row.peak_rpe }}
                </span>
              </li>
            </ol>
          </section>
          <!-- 08 · 进步榜 / 退步名单（跨 12 列） -->
          <section class="bs-panel bs-grid__board">
            <LaneDivider :index="8" tone="ink" level="moss" label="PROGRESS" />
            <div class="t-subhead">
              <span class="bs-panel__title">进步榜 / 退步名单</span>
              <span class="bs-panel__aside">
                比的是「上一次小测 vs 这一次」（<strong>不是</strong>本周的班内百分位）
              </span>
            </div>
            <ProgressBoard
              v-if="blocks"
              :board="blocks.progress_board"
              tone="ink"
              :limit-top="5"
              :limit-regressed="5"
              :name-of="nameOfStudent"
              caption="读的是 blocks.progress_board（约束第 12 条：不要自己调 /api/mini-tests/normalized 拼榜 —— 算式同源但窗口不同）。"
            />
          </section>

        </div>
      </Transition>
    </template>
  </div>
</template>

<style scoped>
/* ⚠️ 这里只写「大屏独有的东西」：外壳、卡片、不对称网格、空态、口令投屏、
   轮播过渡全部在 `styles/teacher.css`（4 个教师端页面共用一个住址）。
   ⚠️ 一个色值都不写死：全部走 tokens.css 的自定义属性。 */

.bs-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
}

.bs-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.bs-alert {
  display: grid;
  grid-template-columns: auto minmax(6em, 1fr);
  grid-template-areas:
    'pill who'
    '. rule';
  gap: 2px var(--space-3);
  align-items: baseline;
  padding: var(--space-2) 0;
  border-block-end: var(--border-hairline-on-ink);
  font-size: var(--fs-bs-small);
}

.bs-alert:last-child {
  border-block-end: none;
}

.bs-alert > .pill {
  grid-area: pill;
  /* ⚠️ 大屏的字号下限是 18px，而 `.pill` 的缺省是 --fs-micro（11px）→ 抬上来 */
  font-size: var(--fs-bs-small);
  padding: 2px var(--space-2);
}

.bs-alert__who {
  grid-area: who;
  color: var(--paper);
  text-decoration: none;
  border-block-end: 1px solid transparent;
}

.bs-alert__who:hover {
  border-block-end-color: var(--track-on-ink);
}

.bs-alert__id {
  color: var(--paper-faint);
  /* ⚠️ 不用 `0.86em`：大屏的字号下限是 18px，而 `.bs-alert` 已经是
     `--fs-bs-small`（18px），0.86em 会掉到 15.5px。 */
  font-size: var(--fs-bs-small);
}

.bs-alert__rule {
  grid-area: rule;
  color: var(--paper-soft);
}

.bs-alert__nums {
  grid-area: rule;
  color: var(--paper-faint);
}

.bs-ok {
  color: var(--moss-on-ink);
}

.bs-bad {
  color: var(--amber-on-ink);
}

/* ------------------------------------------------- 7 天的计时牌条 */
.bs-days {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: var(--space-2);
}

.bs-day {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-2);
  background: var(--ink-sunken);
  border-block-start: var(--lane-thick) solid var(--rule-hairline-on-ink);
  min-width: 0;
}

.bs-day--on {
  border-block-start-color: var(--track-on-ink);
}

.bs-day__d {
  font-size: var(--fs-bs-small);
  color: var(--paper-faint);
  white-space: nowrap;
}

.bs-day__v {
  font-family: var(--font-display);
  font-weight: var(--fw-display-800);
  font-size: var(--fs-bs-title);
  line-height: var(--lh-tight);
  color: var(--paper);
  font-variant-numeric: tabular-nums lining-nums;
}

.bs-day__n {
  font-size: var(--fs-bs-small);
  color: var(--paper-soft);
}

/* ------------------------------------------------- 口令那一格的表单 */
.bs-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.bs-field .caps {
  font-size: var(--fs-bs-small);
  color: var(--paper-soft);
}

.bs-select {
  width: 100%;
  padding: var(--space-2);
  background: var(--ink-sunken);
  border: 1px solid var(--rule-hairline-on-ink);
  border-radius: var(--radius-sharp);
  color: var(--paper);
  font-family: var(--font-data);
  font-size: var(--fs-bs-small);
}

/* ⚠️ `t-subhead` 的粗线在浅底是 `--ink`；大屏上要换成纸色，否则线在墨底上看不见 */
.bs-panel :deep(.t-subhead) {
  border-block-end-color: var(--paper);
}

.bs-panel :deep(.t-subhead__title) {
  font-size: var(--fs-bs-small);
  color: var(--paper-soft);
}
</style>
