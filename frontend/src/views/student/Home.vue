<script setup lang="ts">
/**
 * `views/student/Home.vue` —— 学生端首页（`/s/home`）。
 *
 * ---------------------------------------------------------------------------
 * 读的端点（**实测路径**，出处见 task-2-report.md 第 2 节）
 * ---------------------------------------------------------------------------
 *  1. `GET /api/students/{student_id}` · 匿名 —— 拿姓名与学号（深链接进来时
 *     `localStorage` 里没有 `studentLabel`，故不能只靠 store）；
 *  2. `GET /api/students/{student_id}/home?as_of=` · **学生头** —— 一屏的主数据
 *     （9 个键：`student_id / as_of / semester_id / week / stratification /
 *     weekly_sheet / pending_rpe / unread_notifications / badges`）；
 *  3. `GET /api/students/{student_id}/training-logs/completion-rate?semester_id=&week=`
 *     · **学生头** —— 待办里的「训练日未打卡」那一批（`expected_days` − `completed_days`）。
 *     ⚠️ 它的两个查询参数都是**必填**，而它们的值只能从 ② 的 `semester_id` / `week` 来
 *     → 故 ③ 必须排在 ② 之后（不是并发）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 三处「显示成什么」的口径（都是计划约束逐字要求的）
 * ---------------------------------------------------------------------------
 *  - **本周训练量按单位分列，不合并**（约束第 5 条那一族 +
 *    `prescription_stage.py:411-417` 逐字「刻意不加任何跨单位的周总量汇总字段……
 *    48 分钟 + 120 次 = 168 什么？」）。演示库的学生 1 只有 `min` 一种单位，
 *    但红层 `RED-END-ABN-01` + 体成分异常那一档三种单位并存，故这里必须分列。
 *  - **`weekly_volume` 已经乘过 `factor`**（实测：模板第 1 周是 `43.2`、
 *    训练单上是 `34.6` = 43.2 × 0.8）→ **前端不要再乘一次**。
 *  - **`weekly_sheet === null` 与「训练量为 0」是两件事**：前者渲染 `.s-empty`
 *    「本周还没有训练单」，后者渲染 `.s-unknown`「本周训练量未指定」。
 *    同理 `completion_rate === null` 渲染「—」+ 后端那句 `reason`（约束第 10 条）。
 */
import { computed, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { ApiError } from '../../api/client'
import { getCompletionRate, getStudentHome } from '../../api/endpoints'
import type { components } from '../../api/generated/schema'
import SectionHead from '../../components/SectionHead.vue'
import StatBlock from '../../components/StatBlock.vue'
import StudentNav from '../../components/StudentNav.vue'
import { useAsync } from '../../composables/useAsync'
import { useIdentityStore } from '../../stores/identity'
import { useSessionStore } from '../../stores/session'
import {
  UNKNOWN,
  levelOf,
  labelZh,
  mondayOf,
  num,
  shortDate,
  sheetDayToDate,
  stampOf,
  toPercent,
  volumeUnitZh,
  weekdayOf,
} from '../../present'

type Sheet = components['schemas']['WeeklySheetRead']
type Rate = components['schemas']['CompletionRateRead']

const identity = useIdentityStore()
const session = useSessionStore()

interface Loaded {
  home: components['schemas']['StudentHomeRead']
  /** ⚠️ 可能是 `null` 的两种原因要分开：`rate` 为 null = 端点没读到（下面 `rateError` 说为什么），
   *  而 `rate.completion_rate` 为 null = **后端明确说「这一格没有定义」**（`reason` 给理由）。 */
  rate: Rate | null
  rateError: ApiError | null
}

const { data, loading, settled, reload } = useAsync<Loaded | null>(async () => {
  const id = identity.studentId
  if (id === null) return null
  /* ⚠️⚠️ Plan 05B 修的一格**既有**失效（不是本波的视觉改动带出来的）：
     旧版这里并发读 `readStudent(id)` = `GET /api/students/{id}`，而 Plan 05A
     把那个端点收成了**教职专用**（`crud.py` 逐字：匿名返回 `birth`，而 birth 是
     绑定口令的验身材料；且「学生页一律走 `/api/students/{id}/home` 那类按人收窄的
     窄端点」）。故一个学生会话打开自己的首页会拿到 **403 forbidden**，
     `Promise.all` 整条 reject → 整屏空白 + 一条红横幅（本波截图取证实测复现）。
     姓名与学号改从**会话**读（`stores/session` 的那份镜像，权威是 `GET /api/auth/me`），
     院系（`department`）在学生侧没有任何窄端点给 → 如实显示 UNKNOWN，
     不猜、不拿别的值顶上去（计划约束第 10 条那一族）。 */
  const home = await getStudentHome(id, { asOf: identity.asOf })
  let rate: Rate | null = null
  let rateError: ApiError | null = null
  if (home.semester_id !== null && home.week !== null) {
    try {
      rate = await getCompletionRate(id, { semesterId: home.semester_id, week: home.week })
    } catch (err) {
      // ⚠️ 只在这里 catch：完成率读不到不该让整屏失败（后端 `home` 自己也是这个口径 ——
      //    `dashboard.py:522-526` 把训练单的两档 404 折成 None，注释逐字「首页是一屏，
      //    一格缺数据不该让整屏失败」）。
      rateError = err instanceof ApiError ? err : null
    }
  }
  return { home, rate, rateError }
})

// ⚠️ 换身份或换业务日都要重读：`as_of` 是查询参数，不是渲染期的过滤条件。
watch([() => identity.studentId, () => identity.asOf], () => void reload())

const home = computed(() => data.value?.home ?? null)
const sheet = computed<Sheet | null>(() => home.value?.weekly_sheet ?? null)

/** 这一周的周一（学期周是**周一起、1-based**，见 `present.ts` 的 `mondayOf`）。 */
const monday = computed(() => mondayOf(identity.asOf))

/* ------------------------------------------------------- 本周训练量（按单位分列） */
interface VolumeRow {
  unit: string
  total: number
  exercises: number
}

const volumes = computed<VolumeRow[]>(() => {
  const current = sheet.value
  if (!current) return []
  // ⚠️ 同一个动作会在多个训练日里各出现一次，而 `weekly_volume` 是**每周**的量
  //    （实测学生 1 的 `shuttle_run` 在 day 1/2/3 三处都是 34.6）→ 按 `exercise_ref`
  //    去重，否则三天就把它数了三遍。
  const byRef = new Map<string, { volume: number; unit: string }>()
  for (const session of current.sessions) {
    for (const block of session.blocks) {
      const prev = byRef.get(block.exercise_ref)
      if (!prev || block.weekly_volume > prev.volume) {
        byRef.set(block.exercise_ref, { volume: block.weekly_volume, unit: block.volume_unit })
      }
    }
  }
  const byUnit = new Map<string, { total: number; exercises: number }>()
  for (const entry of byRef.values()) {
    // ⚠️ `unspecified` 不进合计：它的 `weekly_volume` 实测是 `0.0`
    //    （`demo_bootstrap` 的那批 warning 逐字说「需教师用 VOLUME_SCALE 覆盖」），
    //    而「没指定」不是「0 分钟」（约束第 10 条）。
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

/** 「未指定训练量」的**动作**个数（按 `exercise_ref` 去重，不是按 block 数）。 */
const unspecifiedCount = computed(() => {
  const refs = new Set<string>()
  for (const session of sheet.value?.sessions ?? []) {
    for (const block of session.blocks) {
      if (block.volume_unit === 'unspecified') refs.add(block.exercise_ref)
    }
  }
  return refs.size
})

/* ------------------------------------------------------------- 待办 */
interface Todo {
  key: string
  kind: 'checkin' | 'rpe'
  date: string
  title: string
  meta: string
  to: string
}

const todos = computed<Todo[]>(() => {
  const list: Todo[] = []
  const rate = data.value?.rate
  if (rate) {
    const done = new Set(rate.completed_days)
    // ⚠️ 口径来自后端 `feedback.py:810-817`：`completed_days` 已经把
    //    「补卡（submitted_at 与 log_date 不同日）」「迟交（late）」「休息日打卡」
    //    三种排除掉了 → 这里的「未完成」不等于「库里没有那一行」。
    const focusByDay = new Map<number, string>()
    for (const session of sheet.value?.sessions ?? []) focusByDay.set(session.day, session.focus)
    for (const day of rate.expected_days) {
      if (done.has(day)) continue
      const dayNo = dayFromMonday(monday.value, day)
      list.push({
        key: `checkin:${day}`,
        kind: 'checkin',
        date: day,
        title: `${shortDate(day)} 的训练还没计入完成率`,
        meta: `${weekdayOf(day)}${dayNo ? ` · 训练日 ${dayNo}` : ''}${
          focusByDay.get(dayNo) ? ` · ${focusByDay.get(dayNo)}` : ''
        }`,
        to: `/s/check-in?date=${day}`,
      })
    }
  }
  for (const pending of home.value?.pending_rpe ?? []) {
    list.push({
      key: `rpe:${pending.class_session_id}`,
      kind: 'rpe',
      date: pending.session_date,
      title: `${shortDate(pending.session_date)} 第 ${pending.period} 节的课堂快评还没交`,
      meta: `${weekdayOf(pending.session_date)} · 课次 ${pending.class_session_id} · 口令由老师投屏`,
      to: `/s/rpe?session=${pending.class_session_id}`,
    })
  }
  return list.sort((a, b) => a.date.localeCompare(b.date))
})

/** 日历日期 → 训练单里的 `day`（1 = 周一）。算不出来（不是这一周的）返回 0。 */
function dayFromMonday(mon: string, iso: string): number {
  const a = Date.parse(`${mon}T00:00:00Z`)
  const b = Date.parse(`${iso}T00:00:00Z`)
  if (Number.isNaN(a) || Number.isNaN(b)) return 0
  const diff = Math.round((b - a) / 86_400_000) + 1
  return diff >= 1 && diff <= 7 ? diff : 0
}

/* ------------------------------------------------------------- 分层 */
const strat = computed(() => home.value?.stratification ?? null)

/** 训练单里那一天的日期串，给页头用（微周期第 N 周 × 系数）。 */
const sheetLine = computed(() => {
  const s = sheet.value
  if (!s) return ''
  const days = s.sessions.map((x) => sheetDayToDate(monday.value, x.day)).join('、')
  return `微周期第 ${s.week} 周 · 训练日 ${days || '（本周无训练日）'}`
})
</script>

<template>
  <div class="s-page">
    <StudentNav />

    <!-- ⚠️ 没有身份 → 不假装在加载。`App.vue` 已经在壳上提示过一次，
         这里再给一句**带下一步**的（去点身份切换器），因为那一句在页面之外。 -->
    <div v-if="identity.studentId === null" class="s-empty">
      <svg class="s-empty__mark" viewBox="0 0 88 20" aria-hidden="true">
        <path class="s-empty__mark-line" d="M2 6 H86" />
        <path class="s-empty__mark-hair" d="M2 14 H86" />
      </svg>
      <p class="s-empty__title zh-title">还不知道你是谁</p>
      <p class="s-empty__note">
        本页的四个端点里有三个要<strong>学生本人</strong>的会话
        （<code>pe_session</code> cookie）。请在上面那条会话条上<strong>登出</strong>、
        再用一个学生账号登录。
        <!-- ⚠️⚠️ 改前这一格教用户「在上面的身份切换器里选一个学生（或在 URL 上加
             `?student=4`）」，并举了「演示库里有 60 个学生，其中 4、11、15、17 四个
             既有未读消息又有电子勋章，看起来最满」。三件事都是假的：
             ① 那两条通道都只在**开发档构建**里存在（`IdentitySwitcher.vue` 的
                `v-if="IS_DEV"`；`src/dev/identity-url.ts` 的 `adoptFromUrl` 在生产构建里
                被整个摇掉，守卫是 `npm run check:dist`）；
             ② 「60 个学生」那个数的所有者是后端 `/api/health` 的 `students` 一格
                （`App.vue` 的试用告示读的就是它），本页抄一份就是第二个所有者；
             ③ 「4、11、15、17 看起来最满」是**写死的数据例子**，它随
                `demo.ps1 -Students / -Seed` 变假（终审 I1 那一族）。 -->
      </p>
    </div>

    <div v-else-if="loading && !settled" class="s-loading">
      <span class="s-loading__rule" aria-hidden="true"></span>
      <span>正在读本周的训练单与待办…</span>
    </div>

    <template v-else-if="data">
      <header class="s-head">
        <p class="caps s-head__kicker">
          WEEK {{ num(home?.week ?? null) }} · {{ identity.asOf }} · {{ weekdayOf(identity.asOf) }}
        </p>
        <h2 class="zh-title s-head__title">{{ session.name }} 的本周</h2>
        <p class="s-head__meta">
          学号 <span class="data">{{ session.studentNo ?? UNKNOWN }}</span> ·
          院系 <span class="data">{{ UNKNOWN }}</span> ·
          学期第 {{ num(home?.week ?? null) }} 周 /
          <template v-if="sheet">微周期第 {{ sheet.week }} 周</template>
          <template v-else>本周无训练单</template>
        </p>
      </header>

      <!-- 01 · 计时牌：本周训练量（按单位分列）+ 打卡完成率 -->
      <section class="s-card">
        <SectionHead :index="1" label="VOLUME / RATE" />

        <div v-if="sheet === null" class="s-empty">
          <svg class="s-empty__mark" viewBox="0 0 88 20" aria-hidden="true">
            <path class="s-empty__mark-line" d="M2 6 H86" />
            <path class="s-empty__mark-hair" d="M2 14 H86" />
          </svg>
          <p class="s-empty__title zh-title">本周还没有训练单</p>
          <p class="s-empty__note">
            <code>home.weekly_sheet</code> 是 <code>null</code>。后端把「没有生效处方」
            （<code>no_active_prescription</code>）与「这一天不在微周期里」
            （<code>outside_microcycle</code>）两档 404 都折成了 <code>null</code>
            —— 要分辨是哪一档，请打开「本周训练单」那一页（它调端点自己，两档 code 不同）。
          </p>
        </div>

        <div v-else-if="volumes.length === 0" class="s-unknown">
          <p class="s-unknown__title zh-title">本周训练量未知</p>
          <p class="s-unknown__note">
            训练单在，但每个动作的 <code>volume_unit</code> 都是
            <code>unspecified</code>（{{ unspecifiedCount }} 个动作没定量）。
            ⚠️ 这**不是** 0 分钟：后端把「教师还没用 VOLUME_SCALE 覆盖」如实记成
            「未指定」，前端就不能把它讲成「本周不用练」。
          </p>
        </div>

        <div v-else class="hero">
          <StatBlock
            v-for="row in volumes"
            :key="row.unit"
            :value="row.total"
            :decimals="1"
            :unit="volumeUnitZh(row.unit)"
            :label="`本周训练量 · ${volumeUnitZh(row.unit)}`"
            size="hero"
            :caption="`${row.exercises} 个动作 · 已含本周系数 ${sheet.factor.toFixed(2)}`"
          />
          <p v-if="unspecifiedCount > 0" class="hero__aside">
            另有 {{ unspecifiedCount }} 个附加模块<strong>未指定训练量</strong>（不计入上面的合计）。
          </p>
        </div>

        <div class="rate">
          <StatBlock
            :value="toPercent(data.rate?.completion_rate ?? null)"
            :decimals="1"
            unit="%"
            label="本周打卡完成率"
            size="display"
            :level="
              data.rate && data.rate.completion_rate !== null
                ? data.rate.completion_rate >= 1
                  ? 'moss'
                  : data.rate.completion_rate >= 0.6
                    ? 'amber'
                    : 'red'
                : 'default'
            "
            :caption="
              data.rate
                ? `${data.rate.numerator} / ${data.rate.denominator} 个处方训练日`
                : '读不到完成率'
            "
          />
          <!-- ⚠️ 约束第 10 条：`completion_rate` 为 null 时后端**给了一句 reason**，
               那一格信息量比「无数据」三个字大得多，故原样显示。 -->
          <div v-if="data.rate && data.rate.completion_rate === null" class="s-unknown">
            <p class="s-unknown__title zh-title">完成率没有定义（不是 0%）</p>
            <p class="s-unknown__note">{{ data.rate.reason ?? '后端没有给理由。' }}</p>
          </div>
          <div v-else-if="data.rateError" class="s-notice s-notice--warn">
            <p class="s-notice__title">{{ data.rateError.code }} · {{ data.rateError.status }}</p>
            <p>{{ data.rateError.message }}</p>
          </div>
          <p v-else-if="data.rate" class="rate__rule">
            口径：只按<strong>处方训练日</strong>计；补卡、迟交（22:00 后提交）与休息日打卡
            都<strong>不计入</strong>完成率（<code>feedback.py:810-817</code>）。
          </p>
        </div>

        <p v-if="sheetLine" class="s-block__note">{{ sheetLine }}</p>
      </section>

      <!-- 02 · 待办 -->
      <section class="s-card">
        <SectionHead :index="2" label="TO DO" />
        <div class="s-subhead">
          <span class="s-subhead__title">待办</span>
          <span class="s-subhead__aside">{{ todos.length }} 项</span>
        </div>

        <div v-if="todos.length === 0" class="s-empty">
          <svg class="s-empty__mark" viewBox="0 0 88 20" aria-hidden="true">
            <path class="s-empty__mark-line" d="M2 6 H86" />
            <path class="s-empty__mark-hair" d="M2 14 H52" />
          </svg>
          <p class="s-empty__title zh-title">这一周没有待办</p>
          <p class="s-empty__note">
            应打卡的训练日都计入了完成率，也没有还没交的课堂快评。
            <template v-if="data.rate">
              （分母是 {{ data.rate.denominator }} 个训练日）
            </template>
          </p>
        </div>

        <div v-else class="s-rows">
          <div v-for="todo in todos" :key="todo.key" class="s-todo">
            <span class="s-todo__mark" aria-hidden="true"></span>
            <div class="s-todo__body">
              <p class="s-todo__title">{{ todo.title }}</p>
              <p class="s-todo__meta">{{ todo.meta }}</p>
            </div>
            <RouterLink class="btn s-todo__go" :to="todo.to">
              {{ todo.kind === 'checkin' ? '去打卡' : '去交快评' }}
            </RouterLink>
          </div>
        </div>
      </section>

      <!-- 03 · 我的分层 -->
      <section class="s-card">
        <SectionHead :index="3" label="LAYER" :level="strat ? levelOf(strat.label) : 'default'" />
        <div class="s-subhead">
          <span class="s-subhead__title">我的分层</span>
          <span v-if="strat" class="pill" :class="`pill--${levelOf(strat.label)}`">
            {{ labelZh(strat.label) }}
          </span>
        </div>

        <div v-if="!strat" class="s-empty">
          <p class="s-empty__title zh-title">还没有分层结果</p>
          <p class="s-empty__note">
            <code>home.stratification</code> 是 <code>null</code>：这个学生在
            <code>{{ identity.asOf }}</code> 之前没有算过分层（分层是批处理产物）。
          </p>
        </div>

        <div v-else class="s-rows">
          <div class="s-row">
            <span class="s-row__key">判定理由</span>
            <span class="s-row__val">{{ strat.reason }}</span>
          </div>
          <div class="s-row">
            <span class="s-row__key">命中的决策表行</span>
            <span class="s-row__val">{{ strat.hit_rules.join(' · ') || UNKNOWN }}</span>
          </div>
          <div class="s-row">
            <span class="s-row__key">百分位口径</span>
            <span class="s-row__val">{{ strat.percentile_source }}</span>
          </div>
          <div class="s-row">
            <span class="s-row__key">算于</span>
            <span class="s-row__val">{{ strat.computed_on }}</span>
          </div>
          <p class="strat__why">{{ strat.explanation }}</p>
        </div>
      </section>

      <!-- 04 · 消息与勋章 -->
      <section class="s-card">
        <SectionHead :index="4" label="INBOX / BADGE" />
        <div class="s-subhead">
          <span class="s-subhead__title">消息与勋章</span>
          <RouterLink class="btn btn--ghost" to="/s/notifications">去消息中心</RouterLink>
        </div>

        <div class="inbox">
          <StatBlock
            :value="home?.unread_notifications ?? null"
            label="未读消息"
            unit="条"
            size="body"
          />
          <StatBlock
            :value="home?.badges.count ?? null"
            label="电子勋章"
            unit="枚"
            size="body"
            level="moss"
          />
          <div class="inbox__latest">
            <span class="caps">最近一枚勋章</span>
            <!-- ⚠️ `badges.latest` 是 `datetime | null`：没有勋章时它是 null，
                 故这里显示「—」而不是「无」，更不是 epoch 的 1970。 -->
            <span class="data">{{
              home?.badges.latest ? stampOf(home.badges.latest) : UNKNOWN
            }}</span>
          </div>
        </div>

        <p class="s-block__note">
          勋章 = 本学期至今 <code>GREEN_MASTERY</code> 的条数（本周完成度 100%
          且二次小测有指标改善）。⚠️ 原型不做真实推送，只有站内消息。
        </p>
      </section>
    </template>
  </div>
</template>

<style scoped>
/* ⚠️ 这里只写「首页独有的东西」：外壳、卡片、空态、键值行、待办条目
   全部在 `styles/student.css`（6 个页面共用一个住址）。 */
.hero {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.hero__aside {
  font-size: var(--fs-small);
  color: var(--amber);
}

.rate {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin-block-start: var(--space-5);
  padding-block-start: var(--space-4);
  /* ⚠️ 这一条是**区块内的分隔**，不是区块之间的：用 hairline 而不是分道线
     （`lane.css` 的注释逐字：分道线是区块级的母题，铺满整页识别性反而没了）。 */
  border-block-start: var(--border-hairline);
}

.rate__rule {
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.strat__why {
  margin-block-start: var(--space-3);
  padding: var(--space-3);
  background: var(--surface-sunken);
  border-inline-start: var(--bar-hair) solid var(--primary);
  font-size: var(--fs-small);
  color: var(--ink-soft);
}

.inbox {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--space-5);
}

.inbox__latest {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.inbox__latest .caps {
  color: var(--ink-soft);
}
</style>
