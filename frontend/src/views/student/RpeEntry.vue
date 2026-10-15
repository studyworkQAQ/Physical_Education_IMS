<script setup lang="ts">
/**
 * `views/student/RpeEntry.vue` —— 课堂快评（`/s/rpe`）。
 *
 * ---------------------------------------------------------------------------
 * 读 / 写的端点
 * ---------------------------------------------------------------------------
 *  - `GET  /api/students/{id}/home?as_of=` · **学生头** —— `pending_rpe` 那三格
 *    （`class_session_id / session_date / period`）就是「还没交的课次」；
 *  - `GET  /api/class-sessions` · 匿名泛型 list —— 课次下拉（响应体**不含口令**）；
 *  - `GET  /api/rpe-records`（翻页收集 + 客户端按 `student_id` 过滤）—— 我已交过哪些课次
 *    （⚠️ 一节课一个学生只能交一次，`uq_rpe_record_session_student`），
 *    同时它是 `RpeTrend.vue` 的唯一数据源；
 *  - `POST /api/rpe-records` · **学生头** · 201。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ 口令必须**手输**（计划约束第 15 条）—— 这是设计，不是缺功能
 * ---------------------------------------------------------------------------
 * 学生端**拿不到** `rpe_token`：
 *  ① `ClassSessionRead` 上**没有**这一列（Plan 03 收尾小修波摘掉的）；
 *  ② 泛型 list 也显式 `list_exclude=("rpe_token",)`（实测匿名
 *     `GET /api/class-sessions` 的键集合是
 *     `batch_id,course_section_id,id,period,rpe_opened,session_date`，**不含口令**）；
 *  ③ 读口令的唯一入口 `GET /api/class-sessions/{id}/rpe-token` 挂**教师头**，
 *     匿名调它是 401、学生头调它是 403。
 * 故真实流程是：**教师投屏 → 学生手输 → 提交**。本页因此不提供「自动填入」。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 三个错误码各一句人话（派单逐字要求）
 * ---------------------------------------------------------------------------
 *  - `invalid_rpe_token`（403）口令不匹配；
 *  - `rpe_not_opened`（409）老师还没发起 —— ⚠️ 后端把这一道闸门排在验口令**之前**
 *    （`feedback.py:527-537`），因为没发起时 `rpe_token IS NULL`，先验口令会把
 *    「老师还没点」报成「你口令错了」，而两种提示下**要做的事完全不同**；
 *  - `integrity_conflict`（409）= 「你这一节课已经交过了」。
 *    ⚠️ 计划里那个 `rpe_already_submitted` **不存在**（Task 1 顶回 3 的实测结论）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ RPE 是 **0–10 的 11 个大按钮**，不是滑块
 * ---------------------------------------------------------------------------
 * 375px 下 4 列 × 3 行、每格约 79 × 74px（两个方向都过了 44px 的触控下限），
 * 第 12 格放图例。11 档的中文锚点逐条对译 **Borg CR-10**（0–10 那张，
 * **不是** 6–20 的原始 RPE 表）—— 值域与文字的所有者都在 `present.ts`。
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ApiError } from '../../api/client'
import {
  getStudentHome,
  listClassSessions,
  listMyRpeRecords,
  listOnePage,
  submitRpe,
  truncationNoteOf,
} from '../../api/endpoints'
import type { components } from '../../api/generated/schema'
import type { ClassSessionListItem } from '../../api/types'
import SectionHead from '../../components/SectionHead.vue'
import RpeTrend, { type RpePoint } from '../../components/charts/RpeTrend.vue'
import SuccessMark from '../../components/SuccessMark.vue'
import StudentNav from '../../components/StudentNav.vue'
import { useAsync } from '../../composables/useAsync'
import { useIdentityStore } from '../../stores/identity'
import { RPE_SCALE, UNKNOWN, rpeZh, stampOf, weekdayOf } from '../../present'

type PendingRpe = components['schemas']['PendingRpeRead']

const identity = useIdentityStore()
const route = useRoute()

const { data, loading, settled, reload } = useAsync(async () => {
  const id = identity.studentId
  if (id === null) return null
  const [home, sessions, mine] = await Promise.all([
    getStudentHome(id, { asOf: identity.asOf }),
    listOnePage(listClassSessions, '课次'),
    listMyRpeRecords(id),
  ])
  return {
    home,
    sessions: sessions.items,
    mine: mine.items,
    /** ⚠️ 这一格是 `collectPages`（翻页收集撞到 `cap`）的截断，
     *  与下面那个 `truncation`（**单页**取值没取全）是**两件事**、
     *  两个所有者（都在 `api/endpoints.ts`）。 */
    truncated: mine.truncated,
    /** ⚠️ Plan 06 Task 11 / B4：`listOnePage` 给的「没取全」那一句。 */
    truncation: truncationNoteOf([sessions]),
  }
})

watch([() => identity.studentId, () => identity.asOf], () => void reload())

/* ------------------------------------------------------------- 课次 */
const sessions = computed<ClassSessionListItem[]>(() =>
  [...(data.value?.sessions ?? [])].sort((a, b) =>
    b.session_date.localeCompare(a.session_date) || b.period - a.period,
  ),
)

const pending = computed<PendingRpe[]>(() => data.value?.home.pending_rpe ?? [])

const sessionById = computed(
  () => new Map(sessions.value.map((s) => [s.id, s] as const)),
)

/** 我已交过的课次 id（那一节课再交就是 409）。 */
const submittedIds = computed(() => new Set((data.value?.mine ?? []).map((r) => r.class_session_id)))

function sessionLabel(id: number): string {
  const s = sessionById.value.get(id)
  if (!s) return `课次 ${id}`
  return `${s.session_date}（${weekdayOf(s.session_date)}）第 ${s.period} 节 · 班 ${s.course_section_id}`
}

/* ------------------------------------------------------------- 表单 */
const sessionId = ref<number | null>(null)
const token = ref('')
const rpe = ref<number | null>(null)
const submitting = ref(false)
const stamp = ref(false)
const stampCaption = ref('')
const submitError = ref<ApiError | null>(null)
const lastCreated = ref<components['schemas']['RpeRecordRead'] | null>(null)

/** `?session=N` 的深链接（首页的待办条目带它过来）。 */
function initialSession(): number | null {
  const raw = route.query.session
  const value = Array.isArray(raw) ? raw[0] : raw
  const n = Number(value)
  return value !== null && value !== undefined && value !== '' && Number.isInteger(n) && n > 0
    ? n
    : null
}

// ⚠️ 缺省选「待交清单里的第一节课」；没有待交就选下拉里的第一节（于是页面**总是**
//    有一个可用的课次，而不是一片空白 —— 演示库里 240 条快评把 8 节课都交满了，
//    故 `pending_rpe` 实测恒为空数组）。
watch(
  [pending, sessions],
  () => {
    if (sessionId.value !== null) return
    const fromQuery = initialSession()
    if (fromQuery !== null) {
      sessionId.value = fromQuery
      return
    }
    sessionId.value = pending.value[0]?.class_session_id ?? sessions.value[0]?.id ?? null
  },
  { immediate: true },
)

const chosenSession = computed(() =>
  sessionId.value === null ? null : (sessionById.value.get(sessionId.value) ?? null),
)

const alreadySubmitted = computed(
  () => sessionId.value !== null && submittedIds.value.has(sessionId.value),
)

const rpeOpened = computed(() => chosenSession.value?.rpe_opened ?? false)

const canSubmit = computed(
  () => sessionId.value !== null && rpe.value !== null && token.value.trim() !== '' && !submitting.value,
)

/* ------------------------------------------- `elapsed_seconds`：提交耗时（秒）
   ⚠️ 这一格是 `RpeRecordRead` 的真实字段（spec 的表字段列逐字有「提交耗时秒」），
      但**后端不填它**（`submit_rpe` 只填 `student_id` 与 `submitted_at`）—— 它要的是
      「学生从看到题到按下提交花了多久」，那是**只有前端知道**的量。
      故这里从「选好课次与口令」那一刻起计时（不是从组件挂载：挂载到用户看清
      投屏上的口令之间的那几秒不是作答时间）。                          */
const startedAt = ref<number | null>(null)
const elapsed = ref(0)
let timer = 0

function startClock(): void {
  if (startedAt.value !== null) return
  startedAt.value = performance.now()
  timer = window.setInterval(() => {
    if (startedAt.value !== null) elapsed.value = (performance.now() - startedAt.value) / 1000
  }, 200)
}

watch([sessionId, token], ([id, tk]) => {
  if (id !== null && typeof tk === 'string' && tk.trim() !== '') startClock()
})

onBeforeUnmount(() => {
  if (timer !== 0) window.clearInterval(timer)
})

/* ------------------------------------------------------------- 趋势图的数据 */
const trendPoints = computed<RpePoint[]>(() => {
  const rows = [...(data.value?.mine ?? [])].sort((a, b) =>
    a.submitted_at.localeCompare(b.submitted_at),
  )
  return rows.map((row) => {
    const s = sessionById.value.get(row.class_session_id)
    return {
      rpe: row.rpe,
      label: s ? s.session_date.slice(5) : row.submitted_at.slice(5, 10),
      sub: s ? `第${s.period}节` : `课次${row.class_session_id}`,
    }
  })
})

const trendCaption = computed(() => {
  const rows = data.value?.mine ?? []
  if (rows.length === 0) return ''
  const mean = rows.reduce((a, b) => a + b.rpe, 0) / rows.length
  return `共 ${rows.length} 次 · 均值 ${mean.toFixed(2)} 分${
    data.value?.truncated ? '（⚠️ 收集到上限，可能还有更多）' : ''
  }`
})

/* ------------------------------------------------------------- 提交 */
async function submit(): Promise<void> {
  if (sessionId.value === null || rpe.value === null || submitting.value) return
  submitting.value = true
  submitError.value = null
  stamp.value = false
  // ⚠️ 四个键就是 `RpeSubmitCreate` 的全部（`student_id` 与 `submitted_at` 由服务端填）。
  const body: components['schemas']['RpeSubmitCreate'] = {
    class_session_id: sessionId.value,
    rpe: rpe.value,
    rpe_token: token.value.trim(),
    elapsed_seconds: startedAt.value === null ? null : Math.round(elapsed.value * 10) / 10,
  }
  try {
    const created = await submitRpe(body)
    lastCreated.value = created
    stampCaption.value = `${sessionLabel(created.class_session_id)} · RPE ${created.rpe}（${rpeZh(created.rpe)}）· ${stampOf(created.submitted_at)}`
    stamp.value = true
    token.value = ''
    startedAt.value = null
    elapsed.value = 0
    if (timer !== 0) window.clearInterval(timer)
    timer = 0
    await reload()
  } catch (err) {
    if (!(err instanceof ApiError)) {
      console.error('[rpe] 提交时出了非 ApiError 的异常', err)
      return
    }
    submitError.value = err
    // ⚠️ 本页的三个 code 都是**页面内容**（每一档用户要做的下一步都不同），
    //    故一律不送红色横幅 —— 横幅会把「口令打错了一个字」讲成「系统出事了」。
  }
}

const ADVICE: Record<string, string> = {
  invalid_rpe_token:
    '口令不对。请照着老师投屏上的那一串**重新手输**（注意 0 与 O、1 与 l）——学生端读不到口令，这是设计：口令的存在就是为了挡住「猜一个 class_session_id 乱交」。',
  rpe_not_opened:
    '老师还没有发起这节课的快评。等老师在教师端点「发起课堂快评」并把口令投屏之后再交（口令为空与 rpe_opened 为假是同一档，后端刻意不区分）。',
  integrity_conflict:
    '你这一节课已经交过了。一节课一个学生只能交一次（DB 上有唯一约束）——少了它，连点两次「提交」会让教师端的「课堂 RPE 均值」把你算两遍、已提交名单显示 101%。',
  not_found: '这个课次 id 不存在（下拉里选的那一节可能刚被教师删掉了）。',
  // ⚠️ 改前这两条逐字是「没有带上 `X-Student-Id`。请在身份切换器里选一个学生。」与
  //    「这个学号不在册，或它不是当前请求头里的那个人。」—— Plan 05A 之后身份的唯一
  //    载体是 `pe_session` cookie：`unauthenticated` 那一档的意思是「会话没了/过期了」，
  //    而那个切换器只在**开发档构建**里存在（`v-if="IS_DEV"`）。
  unauthenticated:
    '会话不在了（或已过期）：这一格认的是 pe_session cookie，不是请求头。请在上面那条会话条上登出、再用一个学生账号登录。',
  forbidden: '这个学号不在册，或它不是当前会话里的那个人（两档刻意同形，后端不给区分信号）。',
}

const submitAdvice = computed(() =>
  submitError.value ? (ADVICE[submitError.value.code] ?? '') : '',
)

function pickStep(value: number): void {
  rpe.value = rpe.value === value ? null : value
}

const chosenStep = computed(() => RPE_SCALE.find((s) => s.rpe === rpe.value) ?? null)
</script>

<template>
  <div class="s-page">
    <StudentNav />

    <!-- ⚠️ Plan 06 Task 11 / B4：单页取值被截断时**必须**让用户看见。
         判据与那句话的唯一住址是 `api/endpoints.ts` 的 `listOnePage` /
         `truncationNoteOf`；本处只负责把它画出来（用既有的 note 类，
         ⚠️ 不引新 CSS ⇒ `check:tokens` 一格都不退）。 -->
    <p v-if="data?.truncation" class="s-block__note">{{ data.truncation }}</p>

    <div v-if="identity.studentId === null" class="s-empty">
      <p class="s-empty__title zh-title">还不知道你是谁</p>
      <p class="s-empty__note">
        <code>POST /api/rpe-records</code> 要<strong>学生本人</strong>的会话
        （<code>pe_session</code> cookie），而写进去那一行的 <code>student_id</code>
        由服务端<strong>从会话</strong>取（请求体里没有它，故没法替别人交快评）。
        请在上面那条会话条上<strong>登出</strong>、再用一个学生账号登录。
      </p>
    </div>

    <div v-else-if="loading && !settled" class="s-loading">
      <span class="s-loading__rule" aria-hidden="true"></span>
      <span>正在读课次与我的快评记录…</span>
    </div>

    <template v-else-if="data">
      <header class="s-head">
        <p class="caps s-head__kicker">
          CLASS RPE · 0–10 · {{ identity.asOf }} · {{ weekdayOf(identity.asOf) }}
        </p>
        <h2 class="zh-title s-head__title">课堂快评</h2>
        <p class="s-head__meta">
          这节课有多累？0 = 毫无感觉，10 = 力竭极限。口令请照老师投屏上的那一串手输。
        </p>
      </header>

      <!-- 01 · 待交的课次 -->
      <section class="s-card">
        <SectionHead :index="1" label="PENDING" />
        <div class="s-subhead">
          <span class="s-subhead__title">还没交的课堂快评</span>
          <span class="s-subhead__aside">{{ pending.length }} 节</span>
        </div>

        <!-- ⚠️ 空态要讲清「为什么是空的」：演示库里 8 节课 × 30 人 = 240 条快评，
             每个学生的 pending_rpe 实测恒为空。不解释就会被当成页面坏了。 -->
        <div v-if="pending.length === 0" class="s-empty">
          <svg class="s-empty__mark" viewBox="0 0 88 20" aria-hidden="true">
            <path class="s-empty__mark-line" d="M2 6 H86" />
            <path class="s-empty__mark-hair" d="M2 14 H60" />
          </svg>
          <p class="s-empty__title zh-title">本周没有还没交的快评</p>
          <p class="s-empty__note">
            后端的口径是：本周内、我选课的班、<code>rpe_opened = true</code>、
            而我还<strong>没有</strong>交过的那几节课（<code>dashboard.py:450-487</code>）。
            三周前没交的仍然可以补交（后端刻意不做过期），只是不挂在「今日待办」上。
            要交某一节，请在下面自己挑课次。
          </p>
        </div>

        <div v-else class="s-rows">
          <button
            v-for="item in pending"
            :key="item.class_session_id"
            type="button"
            class="pend"
            :class="{ 'pend--on': sessionId === item.class_session_id }"
            @click="sessionId = item.class_session_id"
          >
            <span class="pend__date num">{{ item.session_date }}</span>
            <span class="pend__meta">{{ weekdayOf(item.session_date) }} · 第 {{ item.period }} 节</span>
            <span class="pend__go caps">{{ sessionId === item.class_session_id ? '已选中' : '选它' }}</span>
          </button>
        </div>
      </section>

      <!-- 02 · 交一次快评 -->
      <section class="s-card">
        <SectionHead :index="2" label="SUBMIT" />
        <div class="s-subhead">
          <span class="s-subhead__title">交一次快评</span>
          <span class="s-subhead__aside">
            用时 <strong class="num">{{ elapsed.toFixed(1) }}</strong> 秒
          </span>
        </div>

        <form class="form" @submit.prevent="submit">
          <label class="field">
            <span class="field__label">课次 class_session_id</span>
            <select
              v-model.number="sessionId"
              class="select"
              name="class_session_id"
              :disabled="sessions.length === 0"
            >
              <option v-if="sessions.length === 0" :value="null">库里还没有课次</option>
              <option v-for="s in sessions" :key="s.id" :value="s.id">
                #{{ s.id }} · {{ s.session_date }}（{{ weekdayOf(s.session_date) }}）第
                {{ s.period }} 节 · 班 {{ s.course_section_id }}
                {{ s.rpe_opened ? '' : ' · ⚠️ 未发起快评' }}
                {{ submittedIds.has(s.id) ? ' · ✅ 我已交过' : '' }}
              </option>
            </select>
          </label>

          <div v-if="chosenSession" class="s-rows">
            <div class="s-row">
              <span class="s-row__key">rpe_opened</span>
              <span class="s-row__val">
                <span class="pill" :class="rpeOpened ? 'pill--green' : 'pill--amber'">
                  {{ rpeOpened ? '已发起' : '未发起' }}
                </span>
              </span>
            </div>
            <div class="s-row">
              <span class="s-row__key">我交过了吗</span>
              <span class="s-row__val">
                {{ alreadySubmitted ? '交过了（再交会 409）' : '还没交' }}
              </span>
            </div>
          </div>

          <label class="field">
            <span class="field__label">课堂口令 rpe_token（**只能手输**）</span>
            <input
              v-model="token"
              class="input token"
              type="text"
              name="rpe_token"
              autocomplete="off"
              spellcheck="false"
              inputmode="text"
              placeholder="老师投屏上的那一串"
            />
          </label>

          <p class="token__why">
            ⚠️ 学生端<strong>拿不到</strong>口令：<code>ClassSessionRead</code> 上没有这一列，
            泛型 list 也把它排掉了，读口令的 <code>/rpe-token</code> 端点挂的是
            <strong>教师头</strong>。这不是缺功能 —— 口令的用途就是挡住
            「猜一个 <code>class_session_id</code> 乱交」（spec §4.5）。
          </p>

          <!-- 11 个大按钮：4 列 × 3 行，第 12 格是图例 -->
          <div class="field">
            <span class="field__label">这节课的自觉受累程度 rpe（0–10）</span>
            <div class="scale" role="radiogroup" aria-label="RPE 0 到 10">
              <button
                v-for="step in RPE_SCALE"
                :key="step.rpe"
                type="button"
                class="step"
                :class="[`step--${step.tone}`, { 'step--on': rpe === step.rpe }]"
                role="radio"
                :aria-checked="rpe === step.rpe"
                @click="pickStep(step.rpe)"
              >
                <span class="step__n num">{{ step.rpe }}</span>
                <span class="step__zh">{{ step.zh }}</span>
              </button>

              <!-- 第 12 格：图例。⚠️ 用它填掉 4×3 网格里那个空位，
                   于是「11 个按钮」不会在最后一行留一个缺口。 -->
              <div class="step step--legend" aria-hidden="true">
                <span class="step__legend-row"><i class="dot dot--calm"></i>0–6 不触发预警</span>
                <span class="step__legend-row"><i class="dot dot--amber"></i>7–8 班均 &gt; 7 触发</span>
                <span class="step__legend-row"><i class="dot dot--red"></i>9–10 连续三次触发减量</span>
              </div>
            </div>
          </div>

          <div class="readout" :class="{ 'readout--on': chosenStep !== null }">
            <span class="readout__n num">{{ rpe === null ? '?' : rpe }}</span>
            <span class="readout__zh zh-title">
              {{ chosenStep ? chosenStep.zh : '还没选' }}
            </span>
            <span class="readout__en display">
              {{ chosenStep ? chosenStep.en : 'PICK ONE' }}
            </span>
          </div>

          <div class="s-actions">
            <button class="btn btn--primary" type="submit" :disabled="!canSubmit">
              {{ submitting ? '正在提交…' : '提交快评' }}
            </button>
            <span class="form__note">
              发出 4 个键：<code>class_session_id / rpe / rpe_token / elapsed_seconds</code>
              （<code>student_id</code> 与 <code>submitted_at</code> 由服务端填）
            </span>
          </div>
        </form>

        <SuccessMark
          :visible="stamp"
          text="已提交"
          :caption="stampCaption"
          tone="primary"
          @done="stamp = false"
        />

        <div v-if="submitError" class="s-notice s-notice--warn">
          <p class="s-notice__title">{{ submitError.code }} · {{ submitError.status }}</p>
          <p v-if="submitAdvice">{{ submitAdvice }}</p>
          <p><code>{{ submitError.message }}</code></p>
        </div>

        <div v-if="lastCreated && !stamp" class="s-rows">
          <div class="s-row">
            <span class="s-row__key">服务端记的 submitted_at</span>
            <span class="s-row__val">{{ stampOf(lastCreated.submitted_at) }}</span>
          </div>
          <div class="s-row">
            <span class="s-row__key">回读的 rpe / elapsed_seconds</span>
            <span class="s-row__val">
              {{ lastCreated.rpe }}（{{ rpeZh(lastCreated.rpe) }}）/
              {{ lastCreated.elapsed_seconds === null ? UNKNOWN : lastCreated.elapsed_seconds }}
            </span>
          </div>
        </div>
      </section>

      <!-- 03 · 我的 RPE 趋势 -->
      <section class="s-card">
        <SectionHead :index="3" label="TREND" />
        <div class="s-subhead">
          <span class="s-subhead__title">我的课堂 RPE 趋势</span>
          <span class="s-subhead__aside">{{ data.mine.length }} 次</span>
        </div>
        <RpeTrend :points="trendPoints" :caption="trendCaption" />
      </section>
    </template>
  </div>
</template>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form__note {
  flex: 1 1 100%;
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.token {
  /* 口令是**一串字符**而不是数字，故字距拉开一点：0/O、1/l 要能分辨 */
  letter-spacing: 0.22em;
  font-size: var(--fs-subtitle);
  text-transform: uppercase;
}

.token__why {
  padding: var(--space-3);
  background: var(--surface-sunken);
  border-inline-start: var(--bar-hair) solid var(--primary);
  font-size: var(--fs-micro);
  color: var(--ink-soft);
}

/* ------------------------------------------------------------- 待交清单 */
.pend {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-3) 0;
  border-block-end: var(--border-hairline);
  text-align: left;
}

.pend:last-child {
  border-block-end: none;
}

.pend--on {
  border-inline-start: var(--bar-accent) solid var(--primary);
  padding-inline-start: var(--space-2);
}

.pend__date {
  font-family: var(--font-ui);
  font-weight: var(--fw-600);
  font-size: var(--fs-body);
}

.pend__meta {
  flex: 1 1 auto;
  font-size: var(--fs-micro);
  color: var(--ink-soft);
}

.pend__go {
  color: var(--primary);
}

/* ------------------------------------------------------------- 11 个大按钮
   ⚠️ 375px 视口 − 两侧出血内边距 32px = 343px 内容宽；4 列 × 3px 间隙
      → 每格约 (343 − 3×6)/4 ≈ 81px 宽、74px 高。两个方向都过了 44px 的触控下限。
      ⚠️ 不用横向滚动的 11 连排：滚出视野的按钮等于不存在，
      而「10 = 力竭」恰恰是最该被看见的那一个（它触发 RED_RPE_SUSTAINED）。   */
.scale {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-2);
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-height: 74px;
  padding: var(--space-2) 2px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-raise);
  color: var(--ink);
}

/* ⚠️ 两条 `line-height` 都改走 `--lh-tight`（改前是紧贴的 1 与 1.2）：
   行内文本盒的高 = 字体 content-area（ascent+descent，实测 Hanken Grotesk 1.30em、
   本机 Noto Sans SC 1.45em），**与 `line-height` 无关**；行高小于它就上下溢出、
   压进相邻行 → §4.1 的重叠守卫报红。实测这一对（`5`/`适中`、`10`/`力竭极限`）
   在挡掉 webfont 时重叠 6px（ratio 0.331 / 0.330）。
   逐字的三组对照实验在 `styles/fonts.css` 的文件头；1.3 那条下界的算式在
   `styles/tokens.css` 的 `--lh-tight`。 */
.step__n {
  font-family: var(--font-ui);
  font-weight: var(--fw-700);
  font-size: 28px;
  line-height: var(--lh-tight);
  font-variant-numeric: tabular-nums lining-nums;
}

.step__zh {
  font-family: var(--font-ui);
  font-size: 10px;
  font-weight: var(--fw-500);
  line-height: var(--lh-tight);
  text-align: center;
  color: var(--ink-soft);
}

/* 语义只在**下沿那一条**上（母题的形状不变，与 lane.css 的 `.lane--red` 同一条口径） */
.step--amber {
  box-shadow: inset 0 calc(-1 * var(--bar-accent)) 0 var(--amber);
}

.step--red {
  box-shadow: inset 0 calc(-1 * var(--bar-accent)) 0 var(--red);
}

.step--on {
  background: var(--primary);
  border-color: var(--primary);
  color: var(--on-primary);
}

.step--on .step__zh {
  color: var(--ink-soft);
}

.step--on.step--red {
}

.step--on.step--amber {
}

.step--legend {
  align-items: flex-start;
  justify-content: flex-start;
  gap: 3px;
  padding: var(--space-2);
  background: var(--surface-sunken);
  border-style: dashed;
}

.step__legend-row {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-micro);
  line-height: 1.25;
  color: var(--ink-soft);
}

.dot {
  flex: 0 0 auto;
  inline-size: 7px;
  block-size: 7px;
  border-radius: 50%;
  background: var(--border);
}

.dot--amber {
  background: var(--amber);
}

.dot--red {
  background: var(--red);
}

/* ------------------------------------------------------------- 计时牌读数 */
.readout {
  display: grid;
  grid-template-columns: auto 1fr;
  grid-template-rows: auto auto;
  column-gap: var(--space-3);
  align-items: baseline;
  padding: var(--space-3) var(--space-4);
  background: var(--surface-sunken);
  border-inline-start: var(--bar-accent) solid var(--border);
}

.readout--on {
  border-inline-start-color: var(--primary);
}

.readout__n {
  grid-row: 1 / span 2;
  font-family: var(--font-ui);
  font-weight: var(--fw-700);
  font-size: var(--fs-display);
  line-height: var(--lh-tight);
  font-variant-numeric: tabular-nums lining-nums;
}

.readout__zh {
  font-size: var(--fs-subtitle);
  font-weight: var(--fw-700);
}

.readout__en {
  font-size: var(--fs-micro);
  letter-spacing: var(--tracking-caps);
  text-transform: uppercase;
  color: var(--ink-faint);
}
</style>
