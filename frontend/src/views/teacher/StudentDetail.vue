<script setup lang="ts">
/**
 * `views/teacher/StudentDetail.vue` —— **学生详情**（`/t/students/:studentId`）。
 *
 * ---------------------------------------------------------------------------
 * 读的端点（⚠️ 全部实测过；**教师身份**下逐个发过一次，状态码写在下面）
 * ---------------------------------------------------------------------------
 *  1. `GET /api/students/{id}` · **匿名** → 200（姓名 / 学号 / 性别 / 出生日期 / 院系 / 年级）；
 *  2. `GET /api/teacher/students/{id}/weekly-sheet?as_of=` · ⚠️ **教师头** → 200。
 *     ⚠️ 计划约束第 14 条：**必须走这一个变体**。学生侧的
 *     `GET /api/students/{id}/weekly-sheet` 挂学生头 → 教师身份实测 **401**。
 *     两者响应体**逐字相同**（后端把函数体抽成了 `_weekly_sheet_response` 两处共用）。
 *     ⚠️ 它过 `require_teaches_student`（判据是 `enrollment ⋈ course_section.teacher_id`，
 *     且两行的 `semester_id` 都必须等于「`as_of` 所属的那个学期」）。
 *     实测：学生 1 选在班 1（T0001）与班 5（T0003），故 T0001 与 T0003 **都**能读他；
 *     而 T0002 读他会 403 `forbidden`。
 *  3. `GET /api/mini-tests/normalized?semester_id=&week=` · **匿名** → 200
 *     （⚠️ Plan 04 Task 3 的小修波把它的教师头摘掉了，此前教师 200 / 学生 401 / 匿名 401）；
 *  4. `GET /api/mini-tests?limit=200` · **匿名** → 200（他的三次小测原始成绩，
 *     且**顺带**给出 `semester_id` 与 `week` —— ③ 的两个查询参数都是必填的）；
 *  5. `GET /api/stratification-results?limit=200` + `GET /api/stratification-results/{id}` ·
 *     **匿名** → 200（当前分层 + 命中规则 + 判定理由 + `input_snapshot`）；
 *  6. `GET /api/alerts?limit=200` · **匿名** → 200（他的预警）；
 *  7. `GET /api/teacher/students/{id}/home?as_of=` · ⚠️ **教师头** → 200
 *     （**Plan 04 收尾波新加的教师侧变体**，见下面那一节）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ `/home` 的教师侧变体：Task 3 顶回的那一条，收尾波落地了
 * ---------------------------------------------------------------------------
 * **Task 3 当时的实测**（教师头 `X-Teacher-Staff-No: T0001`，学生 1，T0001 确实任教他）：
 *
 *     GET /api/students/1/home                          -> 401 unauthenticated
 *     GET /api/students/1/weekly-sheet                  -> 401 unauthenticated
 *     GET /api/students/1/training-logs/completion-rate -> 401 unauthenticated
 *     GET /api/students/1/prescriptions/current         -> 401 unauthenticated
 *     GET /api/students/1/notifications                 -> 401 unauthenticated
 *
 * 即：**学生侧的五个端点一个都不能用教师头读**（它们都 `Depends(current_student)`，
 * 缺 `X-Student-Id` 就是 401），而 `client.ts` **一次只注入一个身份头** →
 * 「教师身份」与「读它们」在结构上互斥。Task 3 因此**降级交付**（分层改走匿名的
 * `stratification-results`、拿不到后端现算的 `explanation`；待办 / 未读数 / 勋章计数
 * 三样点名拿不到），并顶回「正确形状是给 `/home` 加一个教师侧变体」。
 *
 * **收尾波把那条顶回落地了**：后端加了 `GET /api/teacher/students/{id}/home`
 * （挂教师头 + `require_teaches_student`，且**带学期限定**），响应体与学生侧那个端点
 * **逐字相同**（后端把函数体抽成了 `dashboard._student_home_response` 两处共用，
 * 与既有的 `_weekly_sheet_response` 同一条处置）。故本页现在**真的显示**：
 *
 *   `/home` 的那一格            本页怎么显示                                  代价
 *   -------------------------  ------------------------------------------  ----------
 *   `stratification.explanation` 第 01 块**原样显示**那段中文                 无
 *   `weekly_sheet`             ② **教师侧变体**（两档 404 各自有 `code`）     无
 *   `pending_rpe`              第 05 块逐条列出（哪一天、第几节）             无
 *   `unread_notifications`     第 05 块给**计数**（它是学生的未读数，教师看的是
 *                              「他还有几条没读」，不是替他读）              无
 *   `badges`                   第 04 块给 `count` + `latest`（后端算的），
 *                              同时仍把 `GREEN_MASTERY` 的**行**列出来        无
 *
 * ⚠️ 于是 Task 3 那三处「点名拿不到」的降级说明**全部撤掉**，第 05 块从
 * 「教师身份读不到的五个端点」改成「他的今日（`/home` 教师侧变体）」+
 * 一份仍然成立的实测记录（学生侧那五条路径**今天仍然**是 401，那不是缺陷、
 * 是「一个端点一道闸门」的口径；教师端走的是变体）。
 * ⚠️ 剩下三个学生侧端点（`completion-rate` / `prescriptions/current` /
 * `notifications`）本页**不需要**：完成率与处方在训练单那一块里已经给出，
 * 消息列表是学生自己的事（教师要看的是「他还有几条没读」这个计数）。
 */
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ApiError } from '../../api/client'
import {
  getNormalizedScores,
  getTeacherStudentHome,
  getTeacherWeeklySheet,
  listAlerts,
  listMiniTests,
  listStratificationResults,
  readStratificationResult,
  readStudent,
} from '../../api/endpoints'
import type { components } from '../../api/generated/schema'
import type { AlertListItem, MiniTestListItem, StratificationResultListItem } from '../../api/types'
import LaneDivider from '../../components/LaneDivider.vue'
import StatBlock from '../../components/StatBlock.vue'
import TeacherNav from '../../components/TeacherNav.vue'
import { useAsync } from '../../composables/useAsync'
import {
  UNKNOWN,
  alertLevelZh,
  alertStatusZh,
  factorSentenceOf,
  factorToneOf,
  impactZh,
  labelZh,
  levelOf,
  mondayOf,
  num,
  reasonZh,
  sheetDayToDate,
  shortDate,
  sourceZh,
  stampOf,
  text,
  volumeUnitZh,
  weekdayOf,
} from '../../present'
import { useIdentityStore } from '../../stores/identity'

type Sheet = components['schemas']['WeeklySheetRead']
type Block = components['schemas']['AssembledBlockRead']
type Normalized = components['schemas']['NormalizedScoreRead']
type Student = components['schemas']['StudentRead']
type Home = components['schemas']['StudentHomeRead']

/** 教师身份下**实测 401** 的那五个学生侧端点（写在页面上，不藏在代码里）。
 *
 *  ⚠️ **这份清单在收尾波之后仍然逐字为真**（学生侧那五条路径今天还是 401），
 *  而它的**含义变了**：它不再是「本页因此缺哪些数据」的清单，而是
 *  「教师端该走哪一条变体」的路标。⚠️ 前两个已有教师侧变体（`weekly-sheet` 自
 *  Plan 03 Task 8、`home` 自本波），故本页**不再**因它们降级；后三个本页不需要
 *  （理由逐字见文件头注释那张表的末段）。
 *  ⚠️ 刻意**不**把学生侧端点改成「学生或教师任一即可」：一个双身份闸门要判两条规则，
 *  而两条规则的失败码不同（后端 `app/api/routers/prescription.py` 的模块 docstring
 *  逐字写了理由）。 */
const STUDENT_ONLY_ENDPOINTS = [
  {
    path: 'GET /api/students/{id}/home',
    what: '首页那五格（分层 / 训练单 / 待办 / 未读数 / 勋章）',
    instead: 'GET /api/teacher/students/{id}/home（本波新加，响应体逐字相同）',
  },
  {
    path: 'GET /api/students/{id}/weekly-sheet',
    what: '本周训练单',
    instead: 'GET /api/teacher/students/{id}/weekly-sheet（Plan 03 Task 8 加的）',
  },
  {
    path: 'GET /api/students/{id}/training-logs/completion-rate',
    what: '本周打卡完成率',
    instead: '本页不需要：完成率在周报的 checkin_rate_by_layer 里，逐人这一格教师端今天不看',
  },
  {
    path: 'GET /api/students/{id}/prescriptions/current',
    what: '当前生效的处方',
    instead: '本页不需要：训练单那一块已经是处方的展开（factor / reasons / sources）',
  },
  {
    path: 'GET /api/students/{id}/notifications',
    what: '发给他的站内消息',
    instead: '本页不需要：教师看的是「他还有几条没读」这个计数（在 /home 的响应里）',
  },
] as const

const route = useRoute()
const identity = useIdentityStore()

const studentId = computed<number | null>(() => {
  const raw = route.params.studentId
  const value = Number(Array.isArray(raw) ? raw[0] : raw)
  return Number.isInteger(value) && value > 0 ? value : null
})

interface Loaded {
  me: Student
  sheet: Sheet | null
  sheetError: ApiError | null
  /** `/home` 的教师侧变体（本波新接的那一格）。 */
  home: Home | null
  homeError: ApiError | null
  miniTests: MiniTestListItem[]
  stratRows: StratificationResultListItem[]
  /** 最新那一行分层的详情（含 `input_snapshot`，故能拿到 `reason`）。 */
  stratDetail: components['schemas']['StratificationResultRead'] | null
  alerts: AlertListItem[]
}

const { data, loading, settled, reload } = useAsync<Loaded | null>(async () => {
  const id = studentId.value
  if (id === null) return null

  const [me, miniPage, stratPage, alertPage] = await Promise.all([
    readStudent(id),
    listMiniTests({ limit: 200 }),
    listStratificationResults({ limit: 200 }),
    listAlerts({ limit: 200 }),
  ])
  const miniTests = miniPage.items
    .filter((row) => row.student_id === id)
    .sort((a, b) => a.week - b.week)
  const stratRows = stratPage.items
    .filter((row) => row.student_id === id)
    .sort((a, b) => a.computed_on.localeCompare(b.computed_on))
  const latest = stratRows[stratRows.length - 1] ?? null

  // ⚠️ 训练单走**教师侧变体**（约束第 14 条）。两档 404 是常态、不是故障。
  let sheet: Sheet | null = null
  let sheetError: ApiError | null = null
  try {
    sheet = await getTeacherWeeklySheet(id, { asOf: identity.asOf })
  } catch (err) {
    sheetError = err instanceof ApiError ? err : null
    if (!(err instanceof ApiError)) console.error('[weekly-sheet]', err)
  }

  // ⚠️ 首页那一屏也走**教师侧变体**（本波新加）。⚠️ 它**不会** 404：后端刻意把
  //    「任何一格缺数据」都折成 `null`（首页是一屏，一格缺数据不该让整屏失败），
  //    连它内部的 `weekly_sheet` 那一格也是折成 `null` 的（`_sheet_or_none`）。
  //    故本处唯一要分支的错误是 **403 `forbidden`**（当前身份不是他**本学期**的
  //    任课教师）——那一档与训练单同形，故两块给同一句话。
  let home: Home | null = null
  let homeError: ApiError | null = null
  try {
    home = await getTeacherStudentHome(id, { asOf: identity.asOf })
  } catch (err) {
    homeError = err instanceof ApiError ? err : null
    if (!(err instanceof ApiError)) console.error('[home]', err)
  }

  // ⚠️ 分层详情另读一次：list 项**排掉了** `input_snapshot`（那是 8 个
  //    「list 比 `*Read` 少列」的资源之一），而判定理由 `reason` 就住在那个快照里。
  //    ⚠️ `/home` 的 `stratification.input_snapshot` 里也有同一个 `reason`，
  //    但本页**仍然**读详情：`/home` 给的是「`computed_on <= as_of` 的最新一行」，
  //    而本页要显示**全部历史行数**与「有效期」（`valid_from` / `valid_to`），
  //    那两格不在 `/home` 的响应里。两者不是重复读取，是两个不同的问题。
  let stratDetail: components['schemas']['StratificationResultRead'] | null = null
  if (latest !== null) {
    try {
      stratDetail = await readStratificationResult(latest.id)
    } catch (err) {
      if (err instanceof ApiError) console.info('[stratification]', err.code)
      else console.error('[stratification]', err)
    }
  }

  return {
    me,
    sheet,
    sheetError,
    home,
    homeError,
    miniTests,
    stratRows,
    stratDetail,
    alerts: alertPage.items.filter((a) => a.student_id === id),
  }
})

watch([studentId, () => identity.teacherStaffNo, () => identity.asOf], () => void reload())

/* ------------------------------------------------------------- 班内百分位
   ⚠️ `semester_id` 与 `week` 是 ③ 的**必填**查询参数，而它们在教师身份下
      **读不到 `/home`**（那一格 401）。故本页从**他自己的小测行**上取：
      「最近一次小测的那一周」正是教师要看的那一格，且这一档不需要任何推算
      （不去自己折算「as_of 是学期第几周」—— 那是后端 `semester_week_of` 的活，
      前端重算一遍就是第二个所有者）。 */
const weeks = computed(() => [...new Set((data.value?.miniTests ?? []).map((r) => r.week))].sort((a, b) => a - b))
const pickedWeek = ref<number | null>(null)
watch(
  weeks,
  (list) => {
    if (pickedWeek.value !== null && list.includes(pickedWeek.value)) return
    pickedWeek.value = list[list.length - 1] ?? null
  },
  { immediate: true },
)

const normalized = ref<Normalized | null>(null)
const normalizedError = ref<ApiError | null>(null)

watch([pickedWeek, () => data.value !== null], async () => {
  normalized.value = null
  normalizedError.value = null
  const week = pickedWeek.value
  const rows = data.value?.miniTests ?? []
  const row = rows.find((r) => r.week === week)
  if (week === null || !row) return
  try {
    normalized.value = await getNormalizedScores({ semesterId: row.semester_id, week })
  } catch (err) {
    normalizedError.value = err instanceof ApiError ? err : null
    if (!(err instanceof ApiError)) console.error('[normalized]', err)
  }
})

interface MySection {
  sectionId: number
  scoredCount: number
  entry: components['schemas']['NormalizedEntryRead']
  sample: number
  slower: number
  tied: number
  rank: number
}

/** 他在那一周的班内百分位。⚠️ 一个学生**可能在两个班**（演示库上每个人都恰好 2 个：
 *  行政班 + 分层班），那时他在两个班里各有一行、百分位各不相同 ——
 *  实测学生 1 第 6 周：班 1（30 人）折返 15.0、班 5（20 人）折返 7.5。
 *  平铺成一张表就会丢掉「这个分是相对谁算的」。 */
const mySections = computed<MySection[]>(() => {
  const id = studentId.value
  const n = normalized.value
  if (id === null || !n) return []
  const out: MySection[] = []
  for (const section of n.sections) {
    const entry = section.entries.find((e) => e.student_id === id)
    if (!entry) continue
    const scored = section.entries.filter((e) => e.shuttle_score !== null)
    const mine = entry.shuttle_score
    out.push({
      sectionId: section.course_section_id,
      scoredCount: section.scored_count,
      entry,
      sample: scored.length,
      slower: mine === null ? 0 : scored.filter((e) => (e.shuttle_score ?? 0) < mine).length,
      tied: mine === null ? 0 : scored.filter((e) => e.shuttle_score === mine).length,
      rank: mine === null ? 0 : 1 + scored.filter((e) => (e.shuttle_score ?? 0) > mine).length,
    })
  }
  return out
})

const unassigned = computed(() => {
  const id = studentId.value
  return (normalized.value?.unassigned ?? []).some((u) => u.student_id === id)
})

/* ------------------------------------------------------------- 分层 */
const strat = computed(() => data.value?.stratDetail ?? null)
const snapshot = computed(() => {
  const raw = strat.value?.input_snapshot as Record<string, unknown> | undefined
  return raw ?? null
})
const stratReason = computed(() => {
  const value = snapshot.value?.reason
  return typeof value === 'string' ? value : null
})

/* ------------------------------------------------------------- 训练单 */
const monday = computed(() => mondayOf(identity.asOf))
const sessions = computed(() =>
  [...(data.value?.sheet?.sessions ?? [])].sort((a, b) => a.day - b.day),
)

/** 训练量按单位分列（⚠️ 不跨单位求和）。 */
const volumes = computed<{ unit: string; total: number; exercises: number }[]>(() => {
  const sheet = data.value?.sheet
  if (!sheet) return []
  const byRef = new Map<string, { volume: number; unit: string }>()
  for (const session of sheet.sessions) {
    for (const block of session.blocks) {
      const prev = byRef.get(block.exercise_ref)
      if (!prev || block.weekly_volume > prev.volume) {
        byRef.set(block.exercise_ref, { volume: block.weekly_volume, unit: block.volume_unit })
      }
    }
  }
  const byUnit = new Map<string, { total: number; exercises: number }>()
  for (const entry of byRef.values()) {
    if (entry.unit === 'unspecified') continue
    const acc = byUnit.get(entry.unit) ?? { total: 0, exercises: 0 }
    acc.total += entry.volume
    acc.exercises += 1
    byUnit.set(entry.unit, acc)
  }
  return [...byUnit.entries()]
    .map(([unit, acc]) => ({ unit, total: acc.total, exercises: acc.exercises }))
    .filter((row) => row.total > 0)
    .sort((a, b) => b.total - a.total)
})

const unspecifiedCount = computed(() => {
  const refs = new Set<string>()
  for (const session of data.value?.sheet?.sessions ?? []) {
    for (const block of session.blocks) {
      if (block.volume_unit === 'unspecified') refs.add(block.exercise_ref)
    }
  }
  return refs.size
})

function structureOf(block: Block): string {
  const s = block.structure as { sets?: unknown; work_min?: unknown; rest_min?: unknown }
  const parts: string[] = []
  if (typeof s.sets === 'number') parts.push(`${s.sets} 组`)
  if (typeof s.work_min === 'number') parts.push(`做 ${s.work_min} 分`)
  if (typeof s.rest_min === 'number') parts.push(`歇 ${s.rest_min} 分`)
  return parts.length > 0 ? parts.join(' · ') : '—'
}

/* ------------------------------------------------------------- 他的预警 */
const LEVEL_ORDER = ['red', 'yellow', 'green'] as const
const hisAlerts = computed<AlertListItem[]>(() =>
  [...(data.value?.alerts ?? [])].sort(
    (a, b) =>
      LEVEL_ORDER.indexOf(a.level as (typeof LEVEL_ORDER)[number]) -
        LEVEL_ORDER.indexOf(b.level as (typeof LEVEL_ORDER)[number]) ||
      b.triggered_at.localeCompare(a.triggered_at),
  ),
)

/** 他的 `GREEN_MASTERY` 那些**行**（表格里逐条列出来）。
 *
 *  ⚠️ **「勋章数」这个计数本页不再自己数**（Plan 04 收尾波改的）：它取自
 *  `/home` 的 `badges.count`，那是后端 `COUNT(*) WHERE rule_id = GREEN_MASTERY
 *  AND semester_id = 本学期 AND student_id = 他` 的**唯一所有者**。
 *  ⚠️ 于是下面那个列表与那个计数**可以不同**，而且不同是有意义的：
 *  列表是「`GET /api/alerts` 里他的全部 `GREEN_MASTERY` 行」（**跨学期**，
 *  因为那个泛型 list 没有筛选参数），计数是「**本学期**的」。本页把两者都显示，
 *  并在计数那一格旁边点名它是后端按本学期算的——不把一个说成另一个。
 *  ⚠️ Task 3 当时选择「只列行、不给计数」正是因为没有 `/home` 的教师侧变体、
 *  而前端自己数一遍就是那个算式的第二份；变体到位之后计数可以**读**了。 */
const badges = computed(() => hisAlerts.value.filter((a) => a.rule_id === 'GREEN_MASTERY'))

/* ------------------------------------------------------------- /home 的四格
   ⚠️ 一律**直接读**教师侧变体的响应，前端不重算任何一格：
   `explanation` 是后端用 `app.domain.stratify.explain` 从 `input_snapshot` 现算的
   一段中文（前端重建它就是 `explain()` 的第二份实现）；`pending_rpe` 的窗口是
   「本学期周里已经上过、教师发起过快评、而他还没交」的那些课；
   `unread_notifications` 与消息中心共用同一个筛选条件；`badges.count` 见上面。 */
const home = computed(() => data.value?.home ?? null)
const explanation = computed(() => home.value?.stratification?.explanation ?? null)
const pendingRpe = computed(() => home.value?.pending_rpe ?? [])
const unread = computed(() => home.value?.unread_notifications ?? null)
const badgeCount = computed(() => home.value?.badges?.count ?? null)
const badgeLatest = computed(() => home.value?.badges?.latest ?? null)
/** ⚠️ `weekly_sheet` 在契约里是**可选**且可空（`weekly_sheet?: … | null`），
 *  故模板里直接写 `home.weekly_sheet === null` 收窄不掉 `undefined`（vue-tsc 会红）。
 *  这一个 computed 把两档一起折成 `null`，于是模板只有一个判据。 */
const homeSheet = computed(() => home.value?.weekly_sheet ?? null)

/* ------------------------------------------------------------- 快照的两格收窄
   `stratification_result.input_snapshot` 在契约里逐字是 `Record<string, unknown>`
   （28 个键，由后端 `tests/pipeline/test_prescription_stage.py` 钉住），
   故模板要显示它就得先收窄。⚠️ 两个助手**不猜**：不是 `number` / `string`
   就返回 `null`，而 `null` 在页面上是「—」，不是 `0`（约束第 10 条）。
   ⚠️ 它们住在 `<script setup>` 里而不是另开一个普通 `<script>` 块导出：
      只有 setup 作用域的顶层绑定才会被模板看见。 */
function toNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function toStr(value: unknown): string | null {
  return typeof value === 'string' ? value : null
}
</script>

<template>
  <div class="t-page">
    <TeacherNav />

    <div v-if="studentId === null" class="t-empty">
      <p class="t-empty__title zh-title">这一条 URL 缺一个学号</p>
      <p class="t-empty__note">
        路由是 <code>/t/students/:studentId</code>（Task 1 定的，带一个必填的路径参数），
        而 <code>/t/students</code> 本身不在路由树里。请从上面的导航选一个学生，
        或从大屏的异常名单 / 预警队列的某一行点进来。
      </p>
    </div>

    <div v-else-if="identity.teacherStaffNo === null" class="t-empty">
      <p class="t-empty__title zh-title">还不知道你是哪位老师</p>
      <p class="t-empty__note">
        本页的主端点 <code>GET /api/teacher/students/{id}/weekly-sheet</code> 挂
        <strong><code>X-Teacher-Staff-No</code></strong>，且过
        <code>require_teaches_student</code>（不是本学期任教他的老师 → 403
        <code>forbidden</code>）。请在身份切换器里选一位教师，或加
        <code>?teacher=T0001</code>。
      </p>
    </div>

    <div v-else-if="loading && !settled" class="t-loading">
      <span class="t-loading__rule" aria-hidden="true"></span>
      <span>正在读学生 {{ studentId }} …</span>
    </div>

    <div v-else-if="!data" class="t-empty">
      <p class="t-empty__title zh-title">读不到这个学生</p>
      <p class="t-empty__note">
        <code>GET /api/students/{{ studentId }}</code> 没有回一行。⚠️ 它是
        <strong>匿名</strong>端点，故这一档的意思是「这个 id 不在册」，
        不是「没有权限」。
      </p>
    </div>

    <template v-else>
      <header class="t-head">
        <div>
          <p class="caps t-head__kicker">
            STUDENT · #{{ data.me.id }} · {{ identity.asOf }}（{{ weekdayOf(identity.asOf) }}）·
            任课 {{ identity.teacherStaffNo }}
          </p>
          <h2 class="zh-title t-head__title">{{ data.me.name }}</h2>
          <p class="t-head__meta">
            学号 <span class="data">{{ data.me.student_no }}</span> ·
            {{ text(data.me.department) }} · 年级
            <span class="num">{{ data.me.grade }}</span> ·
            {{ data.me.sex === 'male' ? '男' : data.me.sex === 'female' ? '女' : data.me.sex }} ·
            生于 <span class="data">{{ data.me.birth }}</span>
            <span v-if="strat" class="pill" :class="`pill--${levelOf(strat.label)}`">
              {{ labelZh(strat.label) }}
            </span>
          </p>
        </div>
        <RouterLink class="btn" to="/t/alerts">← 回预警队列</RouterLink>
      </header>

      <!-- 01 · 当前分层 -->
      <section class="t-card lane-block" :style="{ '--lane-index': 0 }">
        <LaneDivider :index="1" :level="strat ? levelOf(strat.label) : 'default'" label="LAYER" />
        <div class="t-subhead">
          <span class="t-subhead__title">当前分层</span>
          <span class="t-subhead__aside">
            <template v-if="strat">
              算于 <span class="data">{{ strat.computed_on }}</span> ·
              共 <span class="num">{{ data.stratRows.length }}</span> 行历史
            </template>
            <template v-else>没有分层行</template>
          </span>
        </div>

        <div v-if="!strat" class="t-empty">
          <p class="t-empty__title zh-title">还没有分层结果</p>
          <p class="t-empty__note">
            <code>stratification_result</code> 里没有 <code>student_id = {{ studentId }}</code>
            的行。分层是<strong>批处理产物</strong>，故这一档意味着「还没跑过每日批处理」。
          </p>
        </div>

        <div v-else class="t-rows">
          <div class="t-row">
            <span class="t-row__key">分层</span>
            <span class="t-row__val">{{ labelZh(strat.label) }}</span>
          </div>
          <div class="t-row">
            <span class="t-row__key">命中的决策表行</span>
            <span class="t-row__val">{{ strat.hit_rules || UNKNOWN }}</span>
          </div>
          <div class="t-row">
            <span class="t-row__key">判定理由</span>
            <span class="t-row__val">{{ text(stratReason) }}</span>
          </div>
          <div class="t-row">
            <span class="t-row__key">可解释性展开</span>
            <span class="t-row__val">
              <template v-if="explanation === null"><span class="unknown">—</span></template>
              <template v-else>{{ explanation }}</template>
            </span>
          </div>
          <div class="t-row">
            <span class="t-row__key">百分位口径</span>
            <span class="t-row__val">{{ strat.percentile_source }}</span>
          </div>
          <div class="t-row">
            <span class="t-row__key">有效期</span>
            <span class="t-row__val">
              {{ strat.valid_from }} →
              <template v-if="strat.valid_to === null">至今（<code>valid_to</code> 为 null）</template>
              <template v-else>{{ strat.valid_to }}</template>
            </span>
          </div>
          <div class="t-row">
            <span class="t-row__key">快照里的几格</span>
            <span class="t-row__val">
              短板 <span class="num">{{ num(toNumber(snapshot?.W)) }}</span> 项 ·
              有效项 <span class="num">{{ num(toNumber(snapshot?.valid_count)) }}</span> ·
              体成分异常
              <template v-if="snapshot?.C === true">是</template>
              <template v-else-if="snapshot?.C === false">否</template>
              <template v-else><span class="unknown">—</span></template>
              · 历史趋势 <span class="data">{{ text(toStr(snapshot?.trend)) }}</span>
            </span>
          </div>
        </div>

        <p class="t-block__why">
          ⚠️ 本块的<strong>表头几格</strong>（分层 / 命中规则 / 判定理由 / 有效期 /
          历史行数）读的是匿名的
          <code>GET /api/stratification-results</code> + 它的详情，而
          <strong>「可解释性展开」那一格读的是 <code>/home</code> 的教师侧变体</strong>
          <code>GET /api/teacher/students/{{ studentId }}/home</code>。
          ⚠️ 为什么分两处：<code>explanation</code> 是后端<strong>在请求时</strong>用
          <code>app.domain.stratify.explain</code> 从 <code>input_snapshot</code>
          重建出来的一段中文，<strong>库里没有这一列</strong>，而重建的逆运算只有
          后端那一个住址（前端自己重建就是 <code>explain()</code> 的第二份实现）；
          而「有效期」与「共几行历史」<strong>不在</strong> <code>/home</code> 的响应里
          （它只给最新那一行）。⚠️ 两处给的是<strong>同一行</strong>分层：
          <code>/home</code> 取「<code>computed_on &lt;= as_of</code> 的最新一行」，
          本块取「按 <code>computed_on</code> 升序的最后一行」，故
          <code>label</code> / <code>hit_rules</code> 两格逐字相同。
          <br />
          ⚠️ <strong>这一格在 Plan 04 Task 3 是拿不到的</strong>（那时 <code>/home</code>
          只有学生侧端点、教师头调它 401），本页当时显示的是同一份快照里的
          <code>reason</code> 并点名说明了信息量少一层。收尾波加了教师侧变体之后
          那段说明<strong>已撤掉</strong>，这里是后端算好的原文。
        </p>
      </section>

      <!-- 02 · 本周训练单（教师侧变体） -->
      <section class="t-card lane-block" :style="{ '--lane-index': 1 }">
        <LaneDivider
          :index="2"
          :level="data.sheet ? factorToneOf(data.sheet.factor) : 'default'"
          label="WEEKLY SHEET"
        />
        <div class="t-subhead">
          <span class="t-subhead__title">本周训练单</span>
          <span class="t-subhead__aside">
            <code>GET /api/teacher/students/{{ studentId }}/weekly-sheet?as_of={{ identity.asOf }}</code>
          </span>
        </div>

        <div v-if="data.sheetError && !data.sheet" class="t-notice">
          <p class="t-notice__title">
            {{ data.sheetError.code }} · {{ data.sheetError.status }}
          </p>
          <p>
            <template v-if="data.sheetError.code === 'no_active_prescription'">
              这一天没有生效的处方。⚠️ 处方不每天重发，「没有」是<strong>常态</strong>、不是故障。
            </template>
            <template v-else-if="data.sheetError.code === 'outside_microcycle'">
              有处方，但 <code>{{ identity.asOf }}</code> 落在它的微周期之外（通常意味着该换处方了）。
            </template>
            <template v-else-if="data.sheetError.code === 'forbidden'">
              当前身份<strong>不是本学期任教他的老师</strong>
              （判据是 <code>enrollment ⋈ course_section.teacher_id</code>，
              且两行的 <code>semester_id</code> 都必须等于「<code>as_of</code> 所属的那个学期」
              → 「上学期教过他」<strong>不等于</strong>「这学期能读他」）。
            </template>
          </p>
          <p><code>{{ data.sheetError.message }}</code></p>
        </div>

        <template v-else-if="data.sheet">
          <!-- ⚠️ 约束第 13 条逐字要求的那一句（所有者是 present.ts） -->
          <p class="sd-factor" :class="`sd-factor--${factorToneOf(data.sheet.factor)}`">
            {{ factorSentenceOf(data.sheet) }}
          </p>
          <div class="t-rows">
            <div class="t-row">
              <span class="t-row__key">微周期第几周</span>
              <span class="t-row__val num">{{ data.sheet.week }}</span>
            </div>
            <div class="t-row">
              <span class="t-row__key">系数 factor</span>
              <span class="t-row__val num">{{ num(data.sheet.factor, 2) }}</span>
            </div>
            <div class="t-row">
              <span class="t-row__key">reasons</span>
              <span class="t-row__val">
                <template v-if="data.sheet.reasons.length === 0"><span class="unknown">—</span></template>
                <template v-else>{{ data.sheet.reasons.map(reasonZh).join('；') }}</template>
              </span>
            </div>
            <div class="t-row">
              <span class="t-row__key">sources</span>
              <span class="t-row__val">
                <template v-if="data.sheet.sources.length === 0"><span class="unknown">—</span></template>
                <template v-else>{{ data.sheet.sources.map(sourceZh).join('；') }}</template>
              </span>
            </div>
            <div class="t-row">
              <span class="t-row__key">本周是否暂停</span>
              <span class="t-row__val">{{ data.sheet.paused ? '是（安全触发暂停）' : '否' }}</span>
            </div>
            <div class="t-row">
              <span class="t-row__key">训练量（按单位分列）</span>
              <span class="t-row__val">
                <template v-if="volumes.length === 0">
                  <span class="unknown">—</span>
                  <span class="t-block__why">
                    （{{ unspecifiedCount }} 个动作的 <code>volume_unit</code> 是
                    <code>unspecified</code>，⚠️ 那不是 0 分钟）
                  </span>
                </template>
                <template v-else>
                  <span v-for="v in volumes" :key="v.unit" class="sd-vol">
                    <strong class="num">{{ v.total.toFixed(1) }}</strong>
                    {{ volumeUnitZh(v.unit) }}（{{ v.exercises }} 个动作）
                  </span>
                </template>
              </span>
            </div>
          </div>

          <p v-if="data.sheet.reasons.length > 1" class="t-unknown">
            <strong>⚠️ {{ data.sheet.reasons.length }} 条 reason 而系数只有一个
            {{ num(data.sheet.factor, 2) }}</strong> ——
            「一处方一周<strong>至多一条</strong> <code>source='auto'</code> 的调整」
            （用户 2026-10-08 裁定）。故同一周命中两条红色规则时，
            <code>alert</code> 表有<strong>两行</strong>、预警队列看得见两条，
            而训练量<strong>只减一次 20%</strong>。这不是 bug（计划约束第 13 条）。
          </p>

          <div v-for="session in sessions" :key="session.day" class="sd-day">
            <p class="sd-day__head zh-title">
              训练日 {{ session.day }}
              <span class="sd-day__date">
                {{ shortDate(sheetDayToDate(monday, session.day)) }}
                {{ weekdayOf(sheetDayToDate(monday, session.day)) }}
              </span>
              <span class="sd-day__focus">{{ session.focus }}</span>
            </p>
            <table class="data-table sd-blocks">
              <thead>
                <tr>
                  <th scope="col">动作</th>
                  <th scope="col">冲击</th>
                  <th scope="col">结构</th>
                  <th scope="col">周量</th>
                  <th scope="col">强度</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="block in session.blocks" :key="block.exercise_ref">
                  <td>
                    {{ block.exercise_name }}
                    <span class="t-block__why"><code>{{ block.exercise_ref }}</code></span>
                  </td>
                  <td>{{ impactZh(block.impact_level) }}</td>
                  <td>{{ structureOf(block) }}</td>
                  <td>
                    <!-- ⚠️ `weekly_volume` **已经乘过 factor**（后端算的），前端不再乘 -->
                    <template v-if="block.volume_unit === 'unspecified'">
                      <span class="unknown">—</span>
                      <span class="t-block__why">未指定</span>
                    </template>
                    <template v-else>
                      <span class="num">{{ block.weekly_volume.toFixed(1) }}</span>
                      {{ volumeUnitZh(block.volume_unit) }}
                    </template>
                  </td>
                  <td class="sd-intensity">{{ block.intensity_text }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </section>

      <!-- 03 · 班内百分位 -->
      <section class="t-card lane-block" :style="{ '--lane-index': 2 }">
        <LaneDivider :index="3" label="PERCENTILE" />
        <div class="t-subhead">
          <span class="t-subhead__title">班内百分位（二次小测）</span>
          <span class="t-subhead__aside">
            <code>GET /api/mini-tests/normalized</code> · <strong>匿名</strong>
          </span>
        </div>

        <div v-if="weeks.length > 1" class="sd-weeks">
          <span class="caps sd-weeks__label">看哪一次</span>
          <button
            v-for="w in weeks"
            :key="w"
            type="button"
            class="sd-weekbtn"
            :class="{ 'sd-weekbtn--on': pickedWeek === w }"
            @click="pickedWeek = w"
          >
            第 {{ w }} 周
          </button>
        </div>

        <div v-if="(data.miniTests ?? []).length === 0" class="t-empty">
          <p class="t-empty__title zh-title">他没有小测成绩</p>
          <p class="t-empty__note">
            <code>mini_test</code> 表里没有 <code>student_id = {{ studentId }}</code> 的行。
            ⚠️ 小测由教师批量录入（<code>POST /api/mini-tests/batch</code>，教师头），
            每两周一次（spec §8.1），故「这一周没有」是常态。
          </p>
        </div>

        <template v-else>
          <table class="data-table sd-scores">
            <thead>
              <tr>
                <th scope="col">周次</th>
                <th scope="col">测于</th>
                <th scope="col">深蹲 30s</th>
                <th scope="col">折返 20m</th>
                <th scope="col">录入人</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in data.miniTests"
                :key="row.id"
                :class="{ 'sd-scores--on': row.week === pickedWeek }"
              >
                <td>第 {{ row.week }} 周</td>
                <td>{{ row.tested_on }}（{{ weekdayOf(row.tested_on) }}）</td>
                <!-- ⚠️ 两格都可空（「没测」）→ 「—」，不是 0 -->
                <td>{{ num(row.squat_30s_count) }}</td>
                <td>{{ num(row.shuttle_20m_s, 1) }}</td>
                <td>{{ text(row.entered_by) }}</td>
              </tr>
            </tbody>
          </table>

          <div v-if="normalizedError" class="t-notice">
            <p class="t-notice__title">
              {{ normalizedError.code }} · {{ normalizedError.status }} —— 班内百分位读不到
            </p>
            <p><code>{{ normalizedError.message }}</code></p>
          </div>

          <div v-else-if="unassigned" class="t-unknown">
            <p class="t-unknown__title zh-title">他不在任何教学班里 → 班内百分位无定义</p>
            <p class="t-unknown__note">
              后端 <code>unassigned</code> 那一支。⚠️ 它顺带把「选课记录漏了一条」这个
              <strong>要修的数据问题</strong>摆到教师面前。
            </p>
          </div>

          <div v-else-if="normalized" class="sd-sects">
            <div v-for="row in mySections" :key="row.sectionId" class="sd-sect">
              <p class="sd-sect__head zh-title">
                教学班 {{ row.sectionId }}
                <span class="sd-sect__n">（班内 {{ row.scoredCount }} 人有成绩）</span>
              </p>

              <!-- ⚠️ 约束第 11 条：`scored_count == 1` → 「无排名」，不是 50.0 -->
              <div v-if="row.scoredCount === 1" class="t-unknown">
                <p class="t-unknown__title zh-title">无排名</p>
                <p class="t-unknown__note">
                  这个班只有 <strong>1</strong> 个人有成绩。后端仍然给了
                  <span class="num">{{ num(row.entry.shuttle_score, 1) }}</span> ——
                  那是标准 percentile rank 公式在 <code>n = 1</code> 时的自洽结果
                  （<code>(0 + 0.5 × 1) / 1 × 100 = 50.0</code>），
                  但它<strong>看起来像真排过名</strong>，故本页显示「无排名」。
                  ⚠️ 演示库上最小的班是 20 人，故这一档走不到。
                </p>
              </div>

              <template v-else>
                <div class="sd-stats">
                  <StatBlock
                    :value="row.entry.composite"
                    :decimals="2"
                    label="小测综合分"
                    caption="两项等权平均（⚠️ 量纲是混的：次数 vs 百分位）"
                  />
                  <StatBlock
                    :value="row.entry.shuttle_score"
                    :decimals="1"
                    label="折返班内百分位"
                    :level="
                      row.entry.shuttle_score === null
                        ? 'default'
                        : row.entry.shuttle_score >= 50
                          ? 'moss'
                          : row.entry.shuttle_score >= 25
                            ? 'amber'
                            : 'red'
                    "
                    :caption="`样本 ${row.sample} 人`"
                  />
                  <StatBlock
                    :value="row.entry.squat_score"
                    :decimals="1"
                    label="深蹲得分"
                    size="body"
                    caption="= 30 秒次数"
                  />
                </div>
                <div class="t-rows">
                  <div class="t-row">
                    <span class="t-row__key">比他慢的人数</span>
                    <span class="t-row__val">
                      <template v-if="row.entry.shuttle_score === null">
                        <span class="unknown">—</span>（他这次没测折返）
                      </template>
                      <template v-else>{{ row.slower }} 人</template>
                    </span>
                  </div>
                  <div class="t-row">
                    <span class="t-row__key">与他并列</span>
                    <span class="t-row__val">
                      <template v-if="row.entry.shuttle_score === null">
                        <span class="unknown">—</span>
                      </template>
                      <template v-else>{{ row.tied }} 人</template>
                    </span>
                  </div>
                  <div class="t-row">
                    <span class="t-row__key">班内名次（折返）</span>
                    <span class="t-row__val">
                      <template v-if="row.entry.shuttle_score === null">
                        <span class="unknown">—</span>
                      </template>
                      <template v-else>第 {{ row.rank }} / {{ row.sample }}</template>
                    </span>
                  </div>
                </div>
              </template>
            </div>
            <p class="t-block__why">
              ⚠️ 他在<strong>两个班</strong>里各有一行、百分位各不相同（演示库上每个人都
              选了一个行政班 + 一个分层班）：后端因此<strong>按教学班分组</strong>而不是平铺
              一张学生表 —— 平铺会丢掉「这个分是相对谁算的」。
              ⚠️ 本页<strong>不</strong>在前端重算百分位（算式只有一个住址
              <code>app/domain/report.py</code>，后端有 AST 守卫数定义份数）。
            </p>
          </div>
        </template>
      </section>

      <!-- 04 · 他的预警 -->
      <section class="t-card lane-block" :style="{ '--lane-index': 3 }">
        <LaneDivider :index="4" level="red" label="HIS ALERTS" />
        <div class="t-subhead">
          <span class="t-subhead__title">他的预警</span>
          <span class="t-subhead__aside">
            {{ hisAlerts.length }} 条 · 其中 <code>GREEN_MASTERY</code>
            {{ badges.length }} 条 ·
            <strong>后端算的勋章数</strong>
            <template v-if="badgeCount === null"><span class="unknown">—</span></template>
            <template v-else><span class="num">{{ badgeCount }}</span> 枚</template>
            <template v-if="badgeLatest !== null">
              （最近一枚 <span class="data">{{ stampOf(badgeLatest) }}</span>）
            </template>
          </span>
        </div>

        <div v-if="hisAlerts.length === 0" class="t-empty">
          <p class="t-empty__title zh-title">他没有预警</p>
          <p class="t-empty__note">
            <code>alert</code> 表里没有 <code>student_id = {{ studentId }}</code> 的行。
          </p>
        </div>

        <table v-else class="data-table">
          <thead>
            <tr>
              <th scope="col">等级</th>
              <th scope="col">规则</th>
              <th scope="col">状态</th>
              <th scope="col">触发于</th>
              <th scope="col">窗口键</th>
              <th scope="col">处置痕迹</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in hisAlerts" :key="a.id">
              <td>
                <span class="pill" :class="`pill--${levelOf(a.level)}`">{{ alertLevelZh(a.level) }}</span>
              </td>
              <td>
                {{ reasonZh(a.rule_id) }}
                <span class="t-block__why"><code>{{ a.rule_id }}</code></span>
              </td>
              <td>{{ alertStatusZh(a.status) }}</td>
              <td>{{ stampOf(a.triggered_at) }}</td>
              <td>{{ a.window_key }}</td>
              <td>
                <template v-if="a.handled_action === null"><span class="unknown">—</span></template>
                <template v-else>{{ a.handled_action }}</template>
              </td>
            </tr>
          </tbody>
        </table>

        <p class="t-block__why">
          ⚠️ 上面<strong>两个数刻意都显示、且不合并</strong>：表格里的
          {{ badges.length }} 条是「<code>GET /api/alerts</code> 里他的全部
          <code>GREEN_MASTERY</code> 行」（那个泛型 list <strong>没有筛选参数</strong>，
          故它是<strong>跨学期</strong>的），而
          <template v-if="badgeCount === null">「—」</template>
          <template v-else>那个 <span class="num">{{ badgeCount }}</span> 枚</template>
          是 <code>/home</code> 的 <code>badges.count</code> —— 后端
          <code>COUNT(*) WHERE rule_id = 'GREEN_MASTERY' AND semester_id = 本学期</code>
          的结果，<strong>前端不自己数</strong>（那会是那个算式的第二份，
          而「本学期」还要再判一次学期）。两者不同不是 bug，是两个不同的问题。
          <br />
          ⚠️ <strong>这一格在 Plan 04 Task 3 是拿不到的</strong>（那时本页只显示行、
          并点名说「不给勋章数这个计数」）。收尾波加了教师侧变体之后那段说明
          <strong>已撤掉</strong>。
          <RouterLink to="/t/alerts">去预警队列处置 →</RouterLink>
        </p>
      </section>

      <!-- 05 · 他的今日（/home 的教师侧变体） -->
      <section class="t-card lane-block" :style="{ '--lane-index': 4 }">
        <LaneDivider :index="5" level="moss" label="HIS TODAY" />
        <div class="t-subhead">
          <span class="t-subhead__title">他的今日</span>
          <span class="t-subhead__aside">
            <code>GET /api/teacher/students/{{ studentId }}/home?as_of={{ identity.asOf }}</code>
            <template v-if="home"> · 学期第 <span class="num">{{ home.week ?? '—' }}</span> 周</template>
          </span>
        </div>

        <div v-if="data.homeError && !home" class="t-notice">
          <p class="t-notice__title">{{ data.homeError.code }} · {{ data.homeError.status }}</p>
          <p>
            <template v-if="data.homeError.code === 'forbidden'">
              当前身份<strong>不是本学期任教他的老师</strong>
              （判据是 <code>enrollment ⋈ course_section.teacher_id</code>，
              且两行的 <code>semester_id</code> 都必须等于「<code>as_of</code> 所属的那个学期」
              → 「上学期教过他」<strong>不等于</strong>「这学期能读他」）。
            </template>
            <template v-else>{{ data.homeError.message }}</template>
          </p>
        </div>

        <template v-else-if="home">
          <div class="t-rows">
            <div class="t-row">
              <span class="t-row__key">待交的课堂快评</span>
              <span class="t-row__val">
                <template v-if="pendingRpe.length === 0">
                  本周没有待交的（<code>pending_rpe</code> 是空数组）
                </template>
                <template v-else>
                  <span class="num">{{ pendingRpe.length }}</span> 节：
                  <span v-for="(item, index) in pendingRpe" :key="item.class_session_id">
                    <template v-if="index > 0">、</template>
                    <span class="data">{{ item.session_date }}</span>
                    第 <span class="num">{{ item.period }}</span> 节
                    （课次 <span class="num">{{ item.class_session_id }}</span>）
                  </span>
                </template>
              </span>
            </div>
            <div class="t-row">
              <span class="t-row__key">他的未读消息</span>
              <span class="t-row__val">
                <template v-if="unread === null"><span class="unknown">—</span></template>
                <template v-else>
                  <span class="num">{{ unread }}</span> 条未读
                  <span class="t-block__why">
                    （这是<strong>他的</strong>未读数：教师看的是「他还有几条没读」，
                    不是替他读。消息正文只有他自己的
                    <code>GET /api/students/{id}/notifications</code> 给得出来）
                  </span>
                </template>
              </span>
            </div>
            <div class="t-row">
              <span class="t-row__key">电子勋章（本学期）</span>
              <span class="t-row__val">
                <template v-if="badgeCount === null"><span class="unknown">—</span></template>
                <template v-else>
                  <span class="num">{{ badgeCount }}</span> 枚
                  <template v-if="badgeLatest !== null">
                    · 最近一枚 <span class="data">{{ stampOf(badgeLatest) }}</span>
                  </template>
                </template>
              </span>
            </div>
            <div class="t-row">
              <span class="t-row__key">本周训练单（本端点里的那一格）</span>
              <span class="t-row__val">
                <template v-if="homeSheet === null">
                  <span class="unknown">—</span>
                  <span class="t-block__why">
                    （<code>/home</code> 刻意把训练单的两档 404 都折成 <code>null</code>：
                    首页是一屏，一格缺数据不该让整屏失败。要看是哪一档请读上面第 02 块
                    ——它走的是<code>weekly-sheet</code> 的教师侧变体，两档各有自己的
                    <code>code</code>）
                  </span>
                </template>
                <template v-else>
                  微周期第 <span class="num">{{ homeSheet.week }}</span> 周 ·
                  系数 <span class="num">{{ num(homeSheet.factor, 2) }}</span>
                  （与第 02 块同一份数据）
                </template>
              </span>
            </div>
          </div>

          <p class="t-block__why">
            ⚠️ <strong>这一整块在 Plan 04 Task 3 是不存在的</strong>：那时
            <code>/home</code> 只有学生侧端点（挂 <code>X-Student-Id</code>），
            教师用自己的头调它是 <strong>401 <code>unauthenticated</code></strong>，
            而 <code>client.ts</code> 一次只注入一个身份头 → 待办 / 未读数 / 勋章计数
            三样<strong>点名拿不到</strong>。收尾波加了教师侧变体（响应体与学生侧
            <strong>逐字相同</strong>：后端把函数体抽成了
            <code>dashboard._student_home_response</code> 两处共用），三样都能显示了，
            那三处降级说明<strong>已撤掉</strong>。
            <br />
            ⚠️ 它过 <code>require_teaches_student</code>，且<strong>带学期限定</strong>
            （<code>enrollment</code> 与 <code>course_section</code> 两行的
            <code>semester_id</code> 都必须等于「<code>as_of</code> 所属的那个学期」）：
            少了那一格，判据会退化成「他<strong>曾经</strong>教过这个学生」。
          </p>
        </template>
      </section>

      <!-- 06 · 学生侧那五条路径的实测记录（⚠️ 是路标，不是缺陷） -->
      <section class="t-card lane-block" :style="{ '--lane-index': 5 }">
        <LaneDivider :index="6" level="amber" label="STUDENT ONLY" />
        <div class="t-subhead">
          <span class="t-subhead__title">教师头调学生侧端点仍然是 401</span>
          <span class="t-subhead__aside">Task 3 的实测原文，收尾波之后逐字仍成立</span>
        </div>
        <div class="t-notice t-notice--warn">
          <p class="t-notice__title">unauthenticated · 401 —— 学生侧的端点只认 X-Student-Id</p>
          <p>
            下面五个端点都 <code>Depends(current_student)</code>，缺
            <code>X-Student-Id</code> 就是 <strong>401 <code>unauthenticated</code></strong>；
            而前端 <code>client.ts</code> <strong>一次只注入一个身份头</strong>
            （<code>stores/identity.ts</code> 的「一次只有一种身份」）→
            「教师身份」与「读它们」在结构上<strong>互斥</strong>。
          </p>
          <pre class="sd-pre">GET /api/students/{{ studentId }}/home                          -> 401 unauthenticated
GET /api/students/{{ studentId }}/weekly-sheet                  -> 401 unauthenticated
GET /api/students/{{ studentId }}/training-logs/completion-rate -> 401 unauthenticated
GET /api/students/{{ studentId }}/prescriptions/current         -> 401 unauthenticated
GET /api/students/{{ studentId }}/notifications                 -> 401 unauthenticated

（请求头一律是 X-Teacher-Staff-No: {{ identity.teacherStaffNo }}；学生 {{ studentId }} 确实由该教师本学期任教）</pre>
          <ul class="sd-list">
            <li v-for="ep in STUDENT_ONLY_ENDPOINTS" :key="ep.path">
              <code>{{ ep.path }}</code> —— {{ ep.what }}
              <br /><strong>教师端走：</strong>{{ ep.instead }}
            </li>
          </ul>
          <p>
            ⚠️ <strong>这不是缺陷，是口径</strong>：后端<strong>刻意不</strong>把学生侧端点
            改成「学生或教师任一即可」——一个双身份闸门要判两条规则，而两条规则的
            失败码不同（学生侧不符是 403、教师侧不任教也是 403，但「两个头都没带」
            是 401 还是 422？），理由逐字写在
            <code>app/api/routers/prescription.py</code> 的模块 docstring 里。
            正确形状是<strong>给需要的数据加一条教师侧变体</strong>：
            <code>weekly-sheet</code> 那一条是 Plan 03 Task 8 加的，
            <code>home</code> 那一条是本波加的（第 05 块就是它）。
          </p>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
/* ⚠️ 外壳 / 卡片 / 网格 / 空态 / 说明块在 `styles/teacher.css`；
   这里只写「学生详情这一页独有的东西」。⚠️ 一个色值都不写死。 */

.sd-factor {
  font-family: var(--font-ui);
  font-weight: var(--fw-700);
  font-size: var(--fs-display);
  line-height: var(--lh-heading);
}

.sd-factor--red {
  color: var(--red);
}
.sd-factor--green {
  color: var(--green);
}

.sd-vol {
  margin-inline-end: var(--space-4);
}

.sd-day {
  margin-block-start: var(--space-4);
  padding-block-start: var(--space-3);
  border-block-start: var(--border-hairline);
}

.sd-day__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-3);
  font-size: var(--fs-subtitle);
  margin-block-end: var(--space-2);
}

.sd-day__date {
  font-family: var(--font-data);
  font-size: var(--fs-small);
  font-weight: var(--fw-400);
  color: var(--ink-faint);
}

.sd-day__focus {
  margin-inline-start: auto;
  font-family: var(--font-ui);
  font-size: var(--fs-small);
  font-weight: var(--fw-500);
  color: var(--primary);
}

.sd-blocks {
  font-size: var(--fs-small);
}

.sd-intensity {
  max-width: 26em;
  color: var(--ink-faint);
}

.sd-weeks {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.sd-weeks__label {
  color: var(--ink-faint);
}

.sd-weekbtn {
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-raise);
  font-family: var(--font-ui);
  font-size: var(--fs-small);
  color: var(--ink-soft);
}

.sd-weekbtn--on {
  border-color: var(--primary);
  background: var(--primary);
  color: var(--on-primary);
}

.sd-scores--on td {
  background: var(--amber-faint);
  font-weight: 600;
}

.sd-sects {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  margin-block-start: var(--space-3);
}

.sd-sect {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding-block: var(--space-3);
  border-block-end: var(--border-hairline);
}

.sd-sect:last-of-type {
  border-block-end: none;
}

.sd-sect__head {
  font-size: var(--fs-subtitle);
  font-weight: var(--fw-700);
}

.sd-sect__n {
  font-family: var(--font-ui);
  font-size: var(--fs-small);
  font-weight: var(--fw-400);
  color: var(--ink-faint);
}

.sd-stats {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-5);
}

.sd-pre {
  margin: 0;
  padding: var(--space-3);
  background: var(--surface-raise);
  border-inline-start: var(--bar-hair) solid var(--primary);
  font-family: var(--font-data);
  font-size: var(--fs-micro);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.sd-list {
  margin: 0;
  padding-inline-start: var(--space-4);
  font-size: var(--fs-small);
}
</style>
