<script setup lang="ts">
/**
 * `views/student/WeeklySheet.vue` —— 本周训练单（`/s/weekly-sheet`）。
 *
 * ---------------------------------------------------------------------------
 * 读的端点
 * ---------------------------------------------------------------------------
 * `GET /api/students/{student_id}/weekly-sheet?as_of=` · **学生头** · 200。
 * ⚠️ 教师读同一份数据要走 `GET /api/teacher/students/{id}/weekly-sheet`
 * （约束第 14 条：两个端点响应体逐字相同，但挂的头不同）—— 那是 Task 3 的事，
 * 本页一律走学生侧这一条。
 *
 * 响应体 6 个键（实测）：`week / factor / reasons / sources / paused / sessions`，
 * `sessions[i]` 是 `AssembledSessionRead`（`day / focus / blocks`），
 * `blocks[j]` 是 `AssembledBlockRead`（10 个键）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 本页最要紧的一格：`factor` 与 `reasons` 的那句话（计划约束第 13 条）
 * ---------------------------------------------------------------------------
 * 「一处方一周**至多一条** `source='auto'` 的调整」（用户 2026-10-08 裁定 A，
 * 写入侧的不变量在 `alert_stage._auto_adjustment_exists`）。故同一周命中两条
 * 红色规则时：`alert` 表有两行、教师端的预警队列看得见两条，而训练单上
 * **只有一个 20% 的减量**。派单逐字要求把这件事说出来：
 *
 *     若 `reasons` 有两条而 `factor` 是 0.8 → 「本周减量 20%（由 2 条红色预警触发）」
 *
 * ⚠️ 而 `factor` 是那一周**全部**调整的**累乘**（`weekly.py:359-361`），
 * 且 `sources` 可以是 `("teacher", "auto")`（两者并存时仍然相乘）—— 故那句话
 * 要按 `sources[i]` 分别数，不能一律说成「红色预警」。
 *
 * ⚠️ `weekly_volume` **已经乘过 `factor`**（实测：模板第 1 周 `43.2` →
 * 训练单 `34.6`）→ 本页显示的每个量都是**减量之后**的，不再乘第二次。
 */
import { computed, watch } from 'vue'

import { ApiError } from '../../api/client'
import { getWeeklySheet } from '../../api/endpoints'
import type { components } from '../../api/generated/schema'
import LaneDivider from '../../components/LaneDivider.vue'
import StudentNav from '../../components/StudentNav.vue'
import { useAsync } from '../../composables/useAsync'
import { useIdentityStore } from '../../stores/identity'
import {
  UNKNOWN,
  factorSentenceOf,
  factorToneOf,
  impactZh,
  mondayOf,
  num,
  reasonZh,
  sheetDayToDate,
  shortDate,
  sourceZh,
  volumeUnitZh,
  weekdayOf,
} from '../../present'

type Sheet = components['schemas']['WeeklySheetRead']
type Block = components['schemas']['AssembledBlockRead']

/** 「没有」而不是「坏了」的两档（`ApiErrorBanner` 也是这个口径：`tone = 'info'`）。 */
const ABSENT_CODES = new Set(['no_active_prescription', 'outside_microcycle'])

const identity = useIdentityStore()

const { data, loading, settled, reload } = useAsync(async () => {
  const id = identity.studentId
  if (id === null) return null
  let sheet: Sheet | null = null
  let absent: ApiError | null = null
  try {
    sheet = await getWeeklySheet(id, { asOf: identity.asOf })
  } catch (err) {
    if (err instanceof ApiError && ABSENT_CODES.has(err.code)) absent = err
    else throw err
  }
  return { sheet, absent }
})

watch([() => identity.studentId, () => identity.asOf], () => void reload())

const sheet = computed<Sheet | null>(() => data.value?.sheet ?? null)
const monday = computed(() => mondayOf(identity.asOf))

/* ------------------------------------------------------------- 系数那句话
   ⚠️ **算式与措辞都搬进了 `present.ts`**（Plan 04 Task 3）：教师端的「学生详情」
      要显示**同一句**（约束第 13 条：「本周减量 20%（由 2 条红色预警触发）」），
      而两个端各写一份的失效形态是「学生端说减了 20%、教师端说减了 36%」。
      本处此前有 `autoCount` / `teacherCount` / `factorSentence` / `factorTone`
      四个 `computed`，现在只剩两个薄薄的转发。 */
const factorSentence = computed(() =>
  sheet.value === null ? '' : factorSentenceOf(sheet.value),
)

const factorTone = computed<'default' | 'red' | 'moss'>(() => factorToneOf(sheet.value?.factor))

/* ------------------------------------------------------------- 一周七日 */
const WEEKDAY = ['一', '二', '三', '四', '五', '六', '日'] as const

interface DayCell {
  day: number
  date: string
  weekday: string
  focus: string | null
  blocks: number
  isToday: boolean
}

/** ⚠️ 7 格**恒在**（不是只画有训练的那几天）：一个只有 3 格的周条会让人
 *  以为「这一周只有 3 天」，而「其余 4 天是休息日」是训练单里真实的信息。 */
const weekStrip = computed<DayCell[]>(() =>
  WEEKDAY.map((zh, i) => {
    const day = i + 1
    const date = sheetDayToDate(monday.value, day)
    const session = sheet.value?.sessions.find((s) => s.day === day) ?? null
    return {
      day,
      date,
      weekday: zh,
      focus: session?.focus ?? null,
      blocks: session?.blocks.length ?? 0,
      isToday: date === identity.asOf,
    }
  }),
)

/** 按 `day` 升序的训练日（后端给的顺序实测已升序，这里显式排一次：
 *  「列表的顺序」不该依赖后端返回序，那是约束第 9 条同一族的教训）。 */
const sessions = computed(() => [...(sheet.value?.sessions ?? [])].sort((a, b) => a.day - b.day))

/* ------------------------------------------------------------- block 的显示串 */
function structureOf(block: Block): string {
  const s = block.structure as { sets?: unknown; work_min?: unknown; rest_min?: unknown }
  const sets = typeof s.sets === 'number' ? s.sets : null
  const work = typeof s.work_min === 'number' ? s.work_min : null
  const rest = typeof s.rest_min === 'number' ? s.rest_min : null
  if (sets === null && work === null) return '模板未给组次结构'
  const parts: string[] = []
  if (sets !== null) parts.push(`${sets} 组`)
  if (work !== null) parts.push(`每组 ${num(work, 1)} 分钟`)
  if (rest !== null) parts.push(`组间休息 ${num(rest, 1)} 分钟`)
  return parts.join(' · ')
}

function hrZoneOf(block: Block): string {
  // ⚠️ `hr_zone` 是 `number[] | null`（实测演示库里全是 null：模板没给心率区间）。
  if (!block.hr_zone || block.hr_zone.length === 0) return UNKNOWN
  if (block.hr_zone.length === 1) return `${block.hr_zone[0]} bpm`
  return `${block.hr_zone[0]}–${block.hr_zone[1]} bpm`
}

function impactLevel(level: string): 'red' | 'amber' | 'moss' {
  if (level === 'high') return 'red'
  if (level === 'medium') return 'amber'
  return 'moss'
}
</script>

<template>
  <div class="s-page">
    <StudentNav />

    <div v-if="identity.studentId === null" class="s-empty">
      <p class="s-empty__title zh-title">还不知道你是谁</p>
      <p class="s-empty__note">
        本端点挂 <code>X-Student-Id</code>，且路径里的学号必须与请求头是同一个人
        （否则 403 <code>forbidden</code>）。请先选一个身份。
      </p>
    </div>

    <div v-else-if="loading && !settled" class="s-loading">
      <span class="s-loading__rule" aria-hidden="true"></span>
      <span>正在装配本周训练单…</span>
    </div>

    <template v-else-if="data">
      <header class="s-head">
        <p class="caps s-head__kicker">
          WEEKLY SHEET · {{ identity.asOf }} · {{ weekdayOf(identity.asOf) }}
        </p>
        <h2 class="zh-title s-head__title">本周训练单</h2>
        <p class="s-head__meta">
          {{ monday }} 起的那一周 ·
          <template v-if="sheet">微周期第 {{ sheet.week }} 周</template>
          <template v-else>没有训练单</template>
        </p>
      </header>

      <!-- ⚠️ 两档「没有」在这里渲染成**页面内容**，不进红色横幅：
           处方不每天重发，「没有」是常态（`ApiErrorBanner` 对这两档也是 tone=info）。 -->
      <section v-if="data.absent" class="s-card lane-block" :style="{ '--lane-index': 0 }">
        <LaneDivider :index="1" label="NOT FOUND" level="amber" />
        <div class="s-unknown">
          <p class="s-unknown__title zh-title">
            {{
              data.absent.code === 'no_active_prescription'
                ? '这一天没有生效的处方'
                : '这一天不在处方的微周期里'
            }}
          </p>
          <p class="s-unknown__note">
            <code>{{ data.absent.code }}</code> · {{ data.absent.status }} ——
            {{ data.absent.message }}
          </p>
          <p class="s-unknown__note">
            ⚠️ 这两档是**不同的下一步**：前者是「等下一次批处理」（处方只在 spec §5.2
            的五条触发之一成立时才生成），后者是「该换处方了」。
            把业务日 <code>as_of</code> 调回
            <code>{{ identity.asOf }}</code> 附近的处方有效期可以验证是哪一档。
          </p>
        </div>
      </section>

      <template v-else-if="sheet">
        <!-- 01 · 本周调整系数 -->
        <section class="s-card lane-block" :style="{ '--lane-index': 0 }">
          <LaneDivider :index="1" label="FACTOR" :level="factorTone" />
          <div class="s-subhead">
            <span class="s-subhead__title">骨架第 {{ sheet.week }} 周 × 本周调整系数</span>
            <span class="s-subhead__aside">×{{ sheet.factor.toFixed(2) }}</span>
          </div>

          <p class="factor" :class="`factor--${factorTone}`">{{ factorSentence }}</p>

          <div v-if="sheet.paused" class="s-notice s-notice--warn">
            <p class="s-notice__title">本周已暂停</p>
            <p>
              <code>paused = true</code>。⚠️ 下面的训练日**照原样列出**（后端
              <code>weekly_sheet_payload</code> 逐字交代：「暂停」与「本周量为 0」
              是两件不同的事，清空 <code>sessions</code> 会让两者在学生端长得一模一样）。
              本周不要按下面的量练，等教师解除暂停。
            </p>
          </div>

          <div v-if="sheet.reasons.length > 0" class="reasons">
            <div v-for="(reason, i) in sheet.reasons" :key="`${reason}-${i}`" class="reason">
              <span class="reason__code data">{{ reason }}</span>
              <span class="reason__zh">{{ reasonZh(reason) }}</span>
              <span class="pill" :class="sheet.sources[i] === 'auto' ? 'pill--red' : 'pill--amber'">
                {{ sourceZh(sheet.sources[i] ?? UNKNOWN) }}
              </span>
            </div>
            <p class="reasons__note">
              ⚠️ <strong>为什么两条红色预警只减了 20%？</strong>
              用户裁定：「一处方一周至多减一次」。<code>factor</code> 是这一周全部调整的
              <strong>累乘</strong>，而 <code>source='auto'</code> 那一档在写入侧就有
              「已有一行就不再写」的闸门（<code>alert_stage._auto_adjustment_exists</code>）——
              否则两条红色规则会把这一周乘成 0.8 × 0.8 = 0.64。
              故教师端的预警队列里看得见<strong>两行红色</strong>，而这里只有<strong>一个减量</strong>：
              这不是 bug，是裁定。
            </p>
          </div>
          <p v-else class="s-block__note">
            这一周没有任何调整：<code>reasons</code> 是空数组，<code>factor</code> 就是模板
            第 {{ sheet.week }} 周的骨架量。
          </p>
        </section>

        <!-- 02 · 一周七日 -->
        <section class="s-card lane-block" :style="{ '--lane-index': 1 }">
          <LaneDivider :index="2" label="SEVEN DAYS" />
          <div class="s-subhead">
            <span class="s-subhead__title">这一周的七天</span>
            <span class="s-subhead__aside">
              训练日 {{ sessions.length }} 天 / 休息日 {{ 7 - sessions.length }} 天
            </span>
          </div>

          <ol class="strip">
            <li
              v-for="cell in weekStrip"
              :key="cell.day"
              class="strip__cell"
              :class="{
                'strip__cell--on': cell.focus !== null,
                'strip__cell--today': cell.isToday,
              }"
            >
              <span class="strip__wd caps">{{ cell.weekday }}</span>
              <span class="strip__d num">{{ cell.date.slice(8) }}</span>
              <span class="strip__tag">{{ cell.focus ?? '休息' }}</span>
            </li>
          </ol>
          <p class="s-block__note">
            粗框的那一天是业务日 <code>{{ identity.asOf }}</code>（{{ weekdayOf(identity.asOf) }}）。
            ⚠️ 训练单里的 <code>day</code> 是「学期周的第几天」（1 = 周一），
            不是微周期周次 —— 上面两个周次是两件事。
          </p>
        </section>

        <!-- 03…N · 每个训练日一块（道次编号从 03 起） -->
        <section
          v-for="(session, si) in sessions"
          :key="session.day"
          class="s-card lane-block"
          :style="{ '--lane-index': 2 + si }"
        >
          <LaneDivider :index="3 + si" :label="`DAY ${session.day}`" />
          <div class="s-subhead">
            <span class="s-subhead__title">
              {{ shortDate(sheetDayToDate(monday, session.day)) }} ·
              {{ weekdayOf(sheetDayToDate(monday, session.day)) }} · {{ session.focus }}
            </span>
            <span class="s-subhead__aside">{{ session.blocks.length }} 个动作</span>
          </div>

          <div v-if="session.blocks.length === 0" class="s-empty">
            <p class="s-empty__title zh-title">这一天没有安排动作</p>
            <p class="s-empty__note">
              训练单给了这一天（<code>day = {{ session.day }}</code>、重点
              「{{ session.focus }}」），但 <code>blocks</code> 是空数组。
            </p>
          </div>

          <ul v-else class="blocks">
            <li v-for="block in session.blocks" :key="block.exercise_ref" class="block">
              <div class="block__head">
                <span class="block__name zh-title">{{ block.exercise_name }}</span>
                <span class="pill" :class="`pill--${impactLevel(block.impact_level)}`">
                  {{ impactZh(block.impact_level) }}
                </span>
              </div>

              <dl class="block__grid">
                <dt>组次</dt>
                <dd>{{ structureOf(block) }}</dd>
                <dt>每周量</dt>
                <dd>
                  <template v-if="block.volume_unit === 'unspecified'">
                    <span class="unknown">未指定</span>
                    <span class="block__why">（附加模块要教师用 VOLUME_SCALE 定量）</span>
                  </template>
                  <template v-else>
                    <strong class="num">{{ num(block.weekly_volume, 1) }}</strong>
                    {{ volumeUnitZh(block.volume_unit) }}
                  </template>
                </dd>
                <dt>每周次数</dt>
                <dd class="num">{{ block.sessions_per_week }} 次</dd>
                <dt>心率区间</dt>
                <dd>{{ hrZoneOf(block) }}</dd>
                <dt>强度</dt>
                <dd class="block__intensity">{{ block.intensity_text }}</dd>
                <dt>动作代号</dt>
                <dd class="data block__ref">{{ block.exercise_ref }}</dd>
              </dl>
            </li>
          </ul>
        </section>
      </template>
    </template>
  </div>
</template>

<style scoped>
.factor {
  font-family: var(--font-ui);
  font-weight: var(--fw-700);
  font-size: var(--fs-subtitle);
  line-height: var(--lh-heading);
  padding-block: var(--space-2);
  border-inline-start: var(--bar-accent) solid var(--primary);
  padding-inline-start: var(--space-3);
}

.factor--red {
  border-inline-start-color: var(--red);
  color: var(--red);
}

.factor--green {
  border-inline-start-color: var(--green);
  color: var(--green);
}

.reasons {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.reason {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-block-end: var(--border-hairline);
}

.reason__code {
  font-size: var(--fs-micro);
  font-weight: 600;
  color: var(--red);
}

.reason__zh {
  flex: 1 1 auto;
  font-size: var(--fs-small);
  color: var(--ink);
}

.reasons__note {
  margin-block-start: var(--space-2);
  padding: var(--space-3);
  background: var(--surface-sunken);
  border-inline-start: var(--bar-hair) solid var(--primary);
  font-size: var(--fs-micro);
  color: var(--ink-soft);
}

/* ------------------------------------------------------------- 七日条 */
.strip {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 3px;
  list-style: none;
  padding: 0;
  margin: 0;
}

.strip__cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: var(--space-2) 2px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-raise);
  color: var(--ink-faint);
  min-width: 0;
}

.strip__cell--on {
  background: var(--primary);
  border-color: var(--primary);
  color: var(--on-primary);
}

/* 「今天」= 分道线的那一条砖红粗线压在上端（母题的第三次复用） */
.strip__cell--today {
  border-block-start: var(--bar-accent) solid var(--primary);
}

.strip__wd {
  font-size: 9px;
}

.strip__d {
  font-family: var(--font-ui);
  font-weight: var(--fw-700);
  font-size: var(--fs-subtitle);
  line-height: 1;
  font-variant-numeric: tabular-nums lining-nums;
}

.strip__tag {
  font-size: 9px;
  line-height: 1.15;
  text-align: center;
  overflow-wrap: anywhere;
}

/* ------------------------------------------------------------- 动作块 */
.blocks {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  list-style: none;
  padding: 0;
  margin: 0;
}

.block {
  padding-block-start: var(--space-3);
  border-block-start: var(--border-hairline);
}

.block:first-child {
  border-block-start: none;
  padding-block-start: 0;
}

.block__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-2);
  margin-block-end: var(--space-2);
}

.block__name {
  font-size: var(--fs-body);
  font-weight: var(--fw-700);
}

.block__grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--space-1) var(--space-3);
  font-size: var(--fs-small);
}

.block__grid dt {
  font-family: var(--font-ui);
  font-weight: var(--fw-600);
  font-size: var(--fs-micro);
  letter-spacing: var(--primarying-caps);
  text-transform: uppercase;
  color: var(--ink-faint);
  white-space: nowrap;
  padding-block-start: 2px;
}

.block__grid dd {
  margin: 0;
  color: var(--ink);
  min-width: 0;
}

.block__why {
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.block__intensity {
  font-size: var(--fs-micro);
  color: var(--ink-soft);
}

.block__ref {
  font-size: var(--fs-micro);
  color: var(--ink-faint);
  overflow-wrap: anywhere;
}
</style>
