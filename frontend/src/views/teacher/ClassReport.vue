<script setup lang="ts">
/**
 * `views/teacher/ClassReport.vue` —— **班级周报**（`/t/report`）。
 *
 * ---------------------------------------------------------------------------
 * 读的端点（⚠️ 全部实测过）
 * ---------------------------------------------------------------------------
 *  1. `GET /api/teachers?limit=200` · **匿名** —— 工号 → `teacher.id`；
 *  2. `GET /api/course-sections?limit=200` · **匿名** —— 「我任教的班」；
 *  3. `GET /api/weekly-class-reports?limit=200` · **匿名** —— 只为了知道
 *     「哪几周**有**周报」（⚠️ 它的 list 项排掉了全部 5 个聚合列，只剩
 *     `suggestion` + 三个 id + 周次 + 生成时刻，故它**不能**替代 ④）；
 *  4. `GET /api/dashboard/weekly-class-report/{course_section_id}?week=` ·
 *     ⚠️ **教师头** —— 5 个 `JsonText` 列全给的那一份（12 列）。
 *  5. `GET /api/students?limit=200` · **匿名** —— `student_id` → 姓名（进步榜上要显示人）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ 本页最要紧的一格：404 `no_weekly_report`（计划约束第 19 条）
 * ---------------------------------------------------------------------------
 * `weekly_class_report` **只在周日**的批处理里生成（判据是
 * `report_stage.REPORT_WEEKDAY = 6`）。故「周中去读本周的周报」必然 404，
 * 而那一档**不是故障**：后端的 `code` 是 `no_weekly_report`（不是通用的
 * `not_found`），message 里还逐字写了「要看本周的实时数据请调
 * `GET /api/dashboard/class/{id}`」。本页把这一档渲染成一块**有解释的区域**
 * + 一个去大屏的按钮，**绝不**渲染成一堆 0（那会把「还没生成」讲成「本周全是 0」）。
 *
 * ⚠️ `week` 缺省时后端取「这个班**已存下来的最新一周**」
 * （`ORDER BY week DESC LIMIT 1`），**不是**「`as_of` 所属的那一周」——
 * 故本页不需要把 `as_of` 传给它，也不会因为「今天是 2026-10-11、演示库的业务日是
 * 2025-10-12」而读到空的。⚠️ 这一点与大屏那个端点**不同**（那一个的 `as_of`
 * 缺省取服务端当天，故必须显式传）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ `suggestion` 原样显示（派单逐字要求）
 * ---------------------------------------------------------------------------
 * 它是后端算好的一句话（演示库 5 份周报全是「维持当前强度」）。
 * 本页**不再判一次**：前端按 `mean_rpe` 自己判一句的失效形态是
 * 「后端说维持、前端说加量」，而两个句子都在同一屏上。
 */
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ApiError } from '../../api/client'
import {
  getWeeklyClassReport,
  listCourseSections,
  listStudents,
  listTeachers,
  listWeeklyClassReports,
} from '../../api/endpoints'
import type { components } from '../../api/generated/schema'
import type { CourseSectionListItem } from '../../api/types'
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
  num,
  rpeAnchorOf,
  rpeToneOf,
  shortDate,
  stampOf,
} from '../../present'
import { useIdentityStore } from '../../stores/identity'

type Report = components['schemas']['WeeklyClassReportRead']
type CourseSection = CourseSectionListItem

const route = useRoute()
const identity = useIdentityStore()

interface Loaded {
  sections: CourseSection[]
  /** 这个班**有**周报的那几个周次（升序）。 */
  weeksBySection: Map<number, number[]>
  nameOf: Map<number, string>
  meStaffNo: string
  meName: string | null
}

const { data, loading, settled, reload } = useAsync<Loaded | null>(async () => {
  const staffNo = identity.teacherStaffNo
  if (staffNo === null) return null
  const [teachers, sections, reports, students] = await Promise.all([
    listTeachers({ limit: 200 }),
    listCourseSections({ limit: 200 }),
    listWeeklyClassReports({ limit: 200 }),
    listStudents({ limit: 200 }),
  ])
  const me = teachers.items.find((t) => t.staff_no === staffNo) ?? null
  const weeksBySection = new Map<number, number[]>()
  for (const row of reports.items) {
    const list = weeksBySection.get(row.course_section_id) ?? []
    list.push(row.week)
    weeksBySection.set(row.course_section_id, list)
  }
  for (const list of weeksBySection.values()) list.sort((a, b) => a - b)
  return {
    sections: sections.items.filter((s) => me !== null && s.teacher_id === me.id),
    weeksBySection,
    nameOf: new Map(students.items.map((s) => [s.id, s.name])),
    meStaffNo: staffNo,
    meName: me?.name ?? null,
  }
})

watch([() => identity.teacherStaffNo, () => identity.asOf], () => void reload())

/* ------------------------------------------------------------- 选班 / 选周 */
const sectionId = ref<number | null>(null)
/** `null` = 不传 `week`，让后端取「已存下来的最新一周」。 */
const week = ref<number | null>(null)
/** 手输一个任意周次（⚠️ 它是**故意**留的：404 `no_weekly_report` 那一档
 *  要能被走到，否则「本周周报将在周日生成」这句话永远是死代码）。 */
const weekInput = ref('')

const sections = computed(() => data.value?.sections ?? [])

watch(
  sections,
  (list) => {
    if (sectionId.value === null && list.length > 0) sectionId.value = list[0].id
  },
  { immediate: true },
)

const availableWeeks = computed<number[]>(() =>
  sectionId.value === null ? [] : (data.value?.weeksBySection.get(sectionId.value) ?? []),
)

/** ⚠️ **周次与班可以从 URL 初始化**（`?section=1&week=5`）。
 *
 *  加这一格的两个理由，第二个是承重的：
 *  1. 一条「看某个班第 5 周的周报」的链接是可以分享的；
 *  2. **它让 404 `no_weekly_report` 那一档变成可取证的**（计划约束第 19 条逐字要求
 *     「显示『本周周报将在周日生成』，不要显示一堆 0」），而 `--dump-dom` 的无头取证
 *     **点不了按钮、也填不了输入框** —— 没有这一格，那个空态就只能靠读代码断言它存在。
 *  ⚠️ 不合格的值一律忽略（退回「后端缺省 = 最新一份」），与
 *     `stores/identity.ts` 的 `adoptFromUrl` 同一条口径。 */
{
  const rawSection = Number(route.query.section)
  if (Number.isInteger(rawSection) && rawSection > 0) sectionId.value = rawSection
  const rawWeek = Number(route.query.week)
  if (Number.isInteger(rawWeek) && rawWeek >= 1) {
    week.value = rawWeek
    weekInput.value = String(rawWeek)
  }
}

/** ⚠️ URL 给过 `?section=` 之后，上面那条 `watch(sections, …)` 不会把它冲掉：
 *  它的判据是 `sectionId.value === null`，而 URL 那一档已经把它填上了。
 *  （本块是**同步**执行的，而那条 watch 要等匿名的三个 list 回来才第一次触发。） */

const activeSection = computed(
  () => sections.value.find((s) => s.id === sectionId.value) ?? null,
)

/* ------------------------------------------------------------- 读那一份周报 */
const report = ref<Report | null>(null)
const reportError = ref<ApiError | null>(null)
const busy = ref(false)
/** 有没有跑过一次（区分「还没开始」与「开始了但 404」）。 */
const fetched = ref(false)

async function load(): Promise<void> {
  if (sectionId.value === null) return
  busy.value = true
  reportError.value = null
  try {
    report.value = await getWeeklyClassReport(sectionId.value, { week: week.value })
  } catch (err) {
    report.value = null
    reportError.value = err instanceof ApiError ? err : null
    if (!(err instanceof ApiError)) console.error('[class-report]', err)
  } finally {
    busy.value = false
    fetched.value = true
  }
}

watch([sectionId, week, () => data.value !== null], () => void load(), { immediate: true })

function pickWeek(value: string): void {
  const n = Number(value)
  week.value = Number.isInteger(n) && n >= 1 ? n : null
  weekInput.value = week.value === null ? '' : String(week.value)
}

const isNoReport = computed(() => reportError.value?.code === 'no_weekly_report')

/* ------------------------------------------------------------- 5 个聚合列 */
const layerCounts = computed<LayerCounts>(() => {
  const by = (report.value?.layer_distribution as { by_layer?: Record<string, number> } | undefined)
    ?.by_layer
  return {
    red: by?.red ?? 0,
    yellow: by?.yellow ?? 0,
    green: by?.green ?? 0,
    insufficient_data: by?.insufficient_data ?? 0,
  }
})

const flow = computed(() => {
  const raw = report.value?.layer_distribution as
    | { flow?: { has_previous?: boolean; entered?: Record<string, number[]>; left?: Record<string, number[]>; appeared?: Record<string, number[]>; disappeared?: Record<string, number[]> } }
    | undefined
  return raw?.flow ?? null
})

/** 四个名单摊平成「方向 × 层 × 人数」，只留**非空**的那些。
 *  ⚠️ `has_previous` 是承重的：四个名单全空有两档成因（学期第一周 / 一周里没人换层），
 *  形状完全相同，故后端给了这一格开关，本页不猜。 */
const flowRows = computed(() => {
  const f = flow.value
  if (!f) return []
  const kinds = [
    { key: 'entered', zh: '流入（变差了）', dir: f.entered },
    { key: 'left', zh: '流出（变好了）', dir: f.left },
    { key: 'appeared', zh: '新出现（首次被分层）', dir: f.appeared },
    { key: 'disappeared', zh: '消失（不再在名册上）', dir: f.disappeared },
  ] as const
  const out: { kind: string; zh: string; layer: string; ids: number[] }[] = []
  for (const kind of kinds) {
    for (const slot of LAYER_SLOTS) {
      const ids = kind.dir?.[slot.key] ?? []
      if (ids.length > 0) out.push({ kind: kind.key, zh: kind.zh, layer: slot.zh, ids })
    }
  }
  return out
})

const rpe = computed(() => {
  const raw = report.value?.rpe_summary as
    | { curve?: ({ day: string; mean: number; submissions: number } | null)[]; mean?: number | null; previous_mean?: number | null; delta?: number | null }
    | undefined
  return raw ?? null
})

const curveCells = computed(() =>
  (rpe.value?.curve ?? []).map((point, i) => ({
    index: i,
    day: point?.day ?? null,
    mean: point?.mean ?? null,
    submissions: point?.submissions ?? null,
  })),
)

const completionRows = computed<CompletionRow[]>(() => {
  const raw = (report.value?.checkin_rate_by_layer ?? {}) as Record<
    string,
    { students?: number; measured?: number; rate?: number | null } | undefined
  >
  return LAYER_SLOTS.map((slot) => {
    const cell = raw[slot.key]
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

const board = computed(() => {
  const raw = report.value?.progress_board as
    | { top_n: number; top: { student_id: number; change_pct: number }[]; regressed: { student_id: number; change_pct: number }[]; unchanged: number; unmeasured: number }
    | undefined
  return raw ?? null
})

const alertSummary = computed(() => {
  const raw = (report.value?.alert_summary ?? {}) as Record<
    string,
    Record<string, number> | undefined
  >
  return ['red', 'yellow', 'green'].map((level) => ({
    level,
    pending: raw[level]?.pending ?? null,
    handled: raw[level]?.handled ?? null,
    ignored: raw[level]?.ignored ?? null,
  }))
})

function nameOfStudent(id: number): string | null {
  return data.value?.nameOf.get(id) ?? null
}

const rpeLevel = computed<'default' | 'red' | 'amber'>(() => {
  const tone = rpeToneOf(rpe.value?.mean ?? null)
  return tone === 'red' ? 'red' : tone === 'amber' ? 'amber' : 'default'
})
</script>

<template>
  <div class="t-page">
    <TeacherNav />

    <div v-if="identity.teacherStaffNo === null" class="t-empty">
      <p class="t-empty__title zh-title">还不知道你是哪位老师</p>
      <p class="t-empty__note">
        <code>GET /api/dashboard/weekly-class-report/{id}</code> 挂
        <strong><code>X-Teacher-Staff-No</code></strong> 且过
        <code>require_teaches_section</code>（不是自己任教的班 → 403
        <code>forbidden</code>）。请在上面的身份切换器里选一位教师，
        或在 URL 上加 <code>?teacher=T0001</code>。
      </p>
    </div>

    <div v-else-if="loading && !settled" class="t-loading">
      <span class="t-loading__rule" aria-hidden="true"></span>
      <span>正在读周报…</span>
    </div>

    <template v-else>
      <header class="t-head">
        <div>
          <p class="caps t-head__kicker">
            WEEKLY CLASS REPORT · 存下来的那一份 · 只在周日生成
          </p>
          <h2 class="zh-title t-head__title">
            班级周报
            <template v-if="report">
              · 第 <span class="num">{{ report.week }}</span> 周
            </template>
          </h2>
          <p class="t-head__meta">
            {{ activeSection?.name ?? UNKNOWN }} ·
            任课 {{ data?.meStaffNo ?? UNKNOWN }}
            <template v-if="data?.meName">（{{ data.meName }}）</template>
            <template v-if="report">
              · 生成于 <span class="data">{{ stampOf(report.generated_at) }}</span>
              · batch #{{ report.batch_id }}
            </template>
          </p>
        </div>

        <div class="t-picker">
          <label class="t-field">
            <span class="caps">教学班（只列我任教的）</span>
            <select v-model="sectionId" class="select">
              <option v-for="s in sections" :key="s.id" :value="s.id">
                #{{ s.id }} · {{ s.name }}
              </option>
            </select>
          </label>
          <label class="t-field">
            <span class="caps">周次</span>
            <span class="t-weeks">
              <button
                type="button"
                class="t-weekbtn"
                :class="{ 't-weekbtn--on': week === null }"
                @click="pickWeek('')"
              >
                最新一份（后端缺省）
              </button>
              <button
                v-for="w in availableWeeks"
                :key="w"
                type="button"
                class="t-weekbtn"
                :class="{ 't-weekbtn--on': week === w }"
                @click="pickWeek(String(w))"
              >
                第 {{ w }} 周
              </button>
              <input
                v-model="weekInput"
                class="input t-weekinput"
                type="number"
                min="1"
                placeholder="指定周次"
                aria-label="指定一个周次（可以是还没有周报的那一周）"
                @change="pickWeek(weekInput)"
              />
            </span>
          </label>
        </div>
      </header>

      <!-- ⚠️⚠️ 404 no_weekly_report：一块**有解释的区域**，不是一堆 0 -->
      <section v-if="isNoReport" class="t-card lane-block" :style="{ '--lane-index': 0 }">
        <LaneDivider :index="1" label="NOT YET" />
        <div class="t-unknown">
          <p class="t-unknown__title zh-title">本周周报将在周日生成</p>
          <p class="t-unknown__note">
            <code>weekly_class_report</code> 只在<strong>周日</strong>的批处理里生成
            （后端判据是 <code>report_stage.REPORT_WEEKDAY = 6</code>，spec §8.5 逐字）。
            后端回的是 <strong>404 <code>no_weekly_report</code></strong>
            —— ⚠️ 不是通用的 <code>not_found</code>，因为「这一周还没有周报」是常态、不是故障。
          </p>
          <p class="t-unknown__note">
            ⚠️ 本页<strong>不会</strong>把这一档渲染成一堆 <code>0</code>：那会把
            「还没生成」讲成「本周三层完成率都是 0%、人均 RPE 是 0 分」，
            而那是关于这个班的三句假话（计划约束第 10 条与第 19 条）。
          </p>
          <p class="t-unknown__note">
            <strong>要看本周的实时数据请去大屏</strong> ——
            <code>GET /api/dashboard/class/{id}</code> 是<strong>现算</strong>的，
            而本端点读的是<strong>存下来的那一行</strong>。同一个周日之后两者逐字相等
            （后端守卫
            <code>test_the_dashboard_and_the_stored_report_agree_on_the_sunday</code>）。
          </p>
          <p class="t-block__why"><code>{{ reportError?.message }}</code></p>
          <RouterLink class="btn btn--primary" to="/t/dashboard">去班级大屏 →</RouterLink>
        </div>
      </section>

      <section
        v-else-if="reportError"
        class="t-card lane-block"
        :style="{ '--lane-index': 0 }"
      >
        <LaneDivider :index="1" label="ERROR" />
        <div class="t-notice t-notice--bad">
          <p class="t-notice__title">
            {{ reportError.code }} · {{ reportError.status }} —— 周报读不到
          </p>
          <p>
            <template v-if="reportError.code === 'forbidden'">
              这个教学班不是当前身份任教的班（后端 <code>require_teaches_section</code>
              的判据是 <code>course_section.teacher_id</code>）。⚠️ 「班不存在」与
              「不是你的班」<strong>刻意同形</strong>，都报 403。
            </template>
            <template v-else-if="reportError.code === 'unauthenticated'">
              没有带上 <code>X-Teacher-Staff-No</code>。
            </template>
          </p>
          <p><code>{{ reportError.message }}</code></p>
        </div>
      </section>

      <div v-else-if="busy && !fetched" class="t-loading">
        <span class="t-loading__rule" aria-hidden="true"></span>
        <span>正在读第 {{ week ?? '最新' }} 周…</span>
      </div>

      <template v-else-if="report">
        <!-- ⚠️ `suggestion` 是后端算好的一句话，**原样显示**、前端不再判一次 -->
        <section class="t-card lane-block t-suggestion" :style="{ '--lane-index': 0 }">
          <LaneDivider :index="1" level="moss" label="SUGGESTION" />
          <p class="caps t-suggestion__kicker">算法建议 · 后端算好的那一句</p>
          <p class="zh-title t-suggestion__text">{{ report.suggestion }}</p>
          <p class="t-block__why">
            ⚠️ 本页<strong>不</strong>按 <code>mean_rpe</code> 再判一次：前端另判一句的
            失效形态是「后端说维持、前端说加量」，而两个句子在同一屏上。
            它的所有者是 <code>app.domain.report</code>。
          </p>
        </section>

        <div class="t-grid">
          <!-- ① layer_distribution -->
          <section class="t-card lane-block t-grid__4" :style="{ '--lane-index': 1 }">
            <LaneDivider :index="2" label="LAYER DISTRIBUTION" />
            <div class="t-subhead">
              <span class="t-subhead__title">① 分层分布</span>
              <span class="t-subhead__aside">
                上周
                <template v-if="flow?.has_previous">有</template>
                <template v-else>无</template>
              </span>
            </div>
            <LayerDonut :counts="layerCounts" center-label="名册" />

            <div v-if="!flow?.has_previous" class="t-unknown">
              <p class="t-unknown__title zh-title">暂无环比数据</p>
              <p class="t-unknown__note">
                <code>flow.has_previous</code> 是 <code>false</code>：这一周之前没有可比的分层。
                ⚠️ 它与「本周无人流动」在形状上<strong>完全相同</strong>
                （四个名单都空），故后端给了这一格开关，本页不猜。
              </p>
            </div>
            <div v-else-if="flowRows.length === 0" class="t-empty">
              <p class="t-empty__title zh-title">本周无人换层</p>
              <p class="t-empty__note">四个名单（流入 / 流出 / 新出现 / 消失）都是空的。</p>
            </div>
            <ul v-else class="t-flow">
              <li v-for="row in flowRows" :key="`${row.kind}-${row.layer}`" class="t-flow__row">
                <span class="t-flow__zh">{{ row.zh }}</span>
                <span class="t-flow__layer">{{ row.layer }}</span>
                <span class="t-flow__ids num">
                  {{ row.ids.map((id) => nameOfStudent(id) ?? `#${id}`).join('、') }}
                </span>
              </li>
            </ul>
          </section>

          <!-- ② rpe_summary -->
          <section class="t-card lane-block t-grid__4" :style="{ '--lane-index': 2 }">
            <LaneDivider :index="3" :level="rpeLevel" label="RPE SUMMARY" />
            <div class="t-subhead">
              <span class="t-subhead__title">② 人均课堂 RPE</span>
              <span class="t-subhead__aside">量表 0–10（Borg CR-10）</span>
            </div>
            <StatBlock
              :value="rpe?.mean ?? null"
              :decimals="2"
              label="本周人均"
              :level="rpeLevel"
              :caption="
                rpe?.mean === null || rpe?.mean === undefined
                  ? '这一周没有课堂快评（不是 0 分）'
                  : `落在「${rpeAnchorOf(rpe.mean)}」那一档`
              "
            />
            <div class="t-rows">
              <div class="t-row">
                <span class="t-row__key">上周人均</span>
                <span class="t-row__val">{{ num(rpe?.previous_mean ?? null, 2) }}</span>
              </div>
              <div class="t-row">
                <span class="t-row__key">环比</span>
                <span class="t-row__val">
                  <template v-if="rpe?.delta === null || rpe?.delta === undefined">
                    <span class="unknown">—</span>
                  </template>
                  <template v-else>
                    {{ rpe.delta > 0 ? '+' : '' }}{{ rpe.delta.toFixed(2) }}
                  </template>
                </span>
              </div>
            </div>
            <div class="t-days">
              <div
                v-for="cell in curveCells"
                :key="cell.index"
                class="t-day"
                :class="{ 't-day--on': cell.mean !== null }"
              >
                <span class="t-day__d caps">{{ cell.day ? shortDate(cell.day) : `第 ${cell.index + 1} 天` }}</span>
                <!-- ⚠️ `null` → 「—」：0 在这套量表上是「毫无感觉」，是一次真实作答 -->
                <span class="t-day__v num">{{ num(cell.mean ?? null, 1) }}</span>
                <span class="t-day__n">{{ cell.submissions === null ? '无快评' : `${cell.submissions} 份` }}</span>
              </div>
            </div>
            <p class="t-block__why">
              ⚠️ <code>curve</code> 恒为 7 格，没有快评的那一天是 <code>null</code>。
              RPE 的语义色阈值取自后端两条规则：<strong>7–8 染琥珀</strong>
              （<code>YELLOW_CLASS_RPE_HIGH</code> 均值 &gt; 7）、
              <strong>9–10 染砖红</strong>（<code>RED_RPE_SUSTAINED</code> 连续 ≥ 9）——
              与学生端快评页那 11 个按钮<strong>同一套锚点</strong>
              （所有者是 <code>present.ts</code> 的 <code>RPE_SCALE</code> 与
              <code>rpeToneOf</code>，两处不各写一份）。
            </p>
          </section>

          <!-- ③ checkin_rate_by_layer -->
          <section class="t-card lane-block t-grid__4" :style="{ '--lane-index': 3 }">
            <LaneDivider :index="4" level="moss" label="CHECK-IN BY LAYER" />
            <div class="t-subhead">
              <span class="t-subhead__title">③ 三层完成率</span>
              <span class="t-subhead__aside">本周</span>
            </div>
            <CompletionBars
              :rows="completionRows"
              caption="⚠️ 某一层的 rate 是 null 时它显示「—」+ 一条空的虚线轨道，**不是** 0%（那一层一个可测的人都没有）。"
            />
          </section>

          <!-- ④ progress_board -->
          <section class="t-card lane-block t-grid__8" :style="{ '--lane-index': 4 }">
            <LaneDivider :index="5" level="moss" label="PROGRESS BOARD" />
            <div class="t-subhead">
              <span class="t-subhead__title">④ 进步榜 / 退步名单</span>
              <span class="t-subhead__aside">
                top_n = <span class="num">{{ board?.top_n ?? UNKNOWN }}</span>
              </span>
            </div>
            <ProgressBoard
              v-if="board"
              :board="board"
              :name-of="nameOfStudent"
              caption="⚠️ 读的是 weekly_class_report.progress_board（约束第 12 条）：不要自己去调 GET /api/mini-tests/normalized 拼榜 —— 两者的算式已统一到一个住址，但窗口不同。"
            />
          </section>

          <!-- ⑤ alert_summary -->
          <section class="t-card lane-block t-grid__4" :style="{ '--lane-index': 5 }">
            <LaneDivider :index="6" level="red" label="ALERT SUMMARY" />
            <div class="t-subhead">
              <span class="t-subhead__title">⑤ 预警汇总</span>
              <RouterLink class="btn btn--ghost" to="/t/alerts">去处置 →</RouterLink>
            </div>
            <table class="data-table t-alerttable">
              <thead>
                <tr>
                  <th scope="col">等级</th>
                  <th scope="col">待处理</th>
                  <th scope="col">已处理</th>
                  <th scope="col">已忽略</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in alertSummary" :key="row.level">
                  <td>
                    <span class="pill" :class="`pill--${row.level === 'red' ? 'red' : row.level === 'yellow' ? 'amber' : 'moss'}`">
                      {{ row.level === 'red' ? '红色' : row.level === 'yellow' ? '黄色' : '绿色' }}
                    </span>
                  </td>
                  <!-- ⚠️ 三格都可能是 null（后端那一档缺键时）→ 「—」，不是 0 -->
                  <td>{{ row.pending === null ? UNKNOWN : row.pending }}</td>
                  <td>{{ row.handled === null ? UNKNOWN : row.handled }}</td>
                  <td>{{ row.ignored === null ? UNKNOWN : row.ignored }}</td>
                </tr>
              </tbody>
            </table>
            <p class="t-block__why">
              ⚠️ 这是<strong>周报生成那一刻</strong>的快照（<code>generated_at</code>
              = {{ stampOf(report.generated_at) }}）。教师之后处置的预警<strong>不会</strong>
              回写这一行 —— 实时的三档计数在大屏的 <code>blocks.alert_summary</code> 上。
              <br />⚠️ 顶栏那个「预警角标」刻意不另给一个计数：它等于三档
              <code>pending</code> 之和，另给一格就是第二个所有者。
            </p>
          </section>
        </div>
      </template>

      <div v-else class="t-empty">
        <p class="t-empty__title zh-title">还没有选教学班</p>
        <p class="t-empty__note">
          当前身份名下 <strong class="num">{{ sections.length }}</strong> 个教学班。
        </p>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* ⚠️ 外壳 / 卡片 / 网格 / 空态 / 说明块全部在 `styles/teacher.css`；
   这里只写「周报这一页独有的东西」。⚠️ 一个色值都不写死。 */

.t-picker {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--space-4);
}

.t-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.t-field .caps {
  color: var(--ink-soft);
}

.t-field .select {
  min-width: 15em;
}

.t-weeks {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.t-weekbtn {
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-raise);
  font-family: var(--font-ui);
  font-size: var(--fs-small);
  color: var(--ink-soft);
}

.t-weekbtn--on {
  border-color: var(--primary);
  background: var(--primary);
  color: var(--on-primary);
}

.t-weekinput {
  width: 8em;
}

/* ------------------------------------------------- 算法建议那一块
   ⚠️ 它是本页**唯一**一块不给数字的：后端已经把这周的判断说成了一句话，
      故它排得最大（年鉴的「编者按」那一档）。 */
.t-suggestion {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.t-suggestion__kicker {
  color: var(--green);
}

.t-suggestion__text {
  font-size: var(--fs-display);
  line-height: var(--lh-heading);
}

/* ------------------------------------------------- 环比流动的名单 */
.t-flow {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.t-flow__row {
  display: grid;
  grid-template-columns: minmax(8em, auto) 5em 1fr;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-block-end: var(--border-hairline);
  font-size: var(--fs-small);
}

.t-flow__row:last-child {
  border-block-end: none;
}

.t-flow__zh {
  color: var(--ink-soft);
}

.t-flow__layer {
  font-weight: var(--fw-500);
}

.t-flow__ids {
  color: var(--ink-faint);
  overflow-wrap: anywhere;
}

/* ------------------------------------------------- 7 天的计时牌条 */
.t-days {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: var(--space-2);
}

.t-day {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-2);
  background: var(--surface-sunken);
  border-block-start: var(--bar-accent) solid var(--border);
  min-width: 0;
}

.t-day--on {
  border-block-start-color: var(--primary);
  background: var(--surface-raise);
}

.t-day__d {
  font-size: var(--fs-micro);
  color: var(--ink-faint);
  white-space: nowrap;
}

.t-day__v {
  font-family: var(--font-ui);
  font-weight: var(--fw-700);
  font-size: var(--fs-title);
  line-height: var(--lh-tight);
  font-variant-numeric: tabular-nums lining-nums;
}

.t-day__n {
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.t-alerttable td,
.t-alerttable th {
  text-align: right;
}

.t-alerttable td:first-child,
.t-alerttable th:first-child {
  text-align: left;
}
</style>
