<script setup lang="ts">
/**
 * `views/student/CheckIn.vue` —— 每日打卡（`/s/check-in`）。
 *
 * ---------------------------------------------------------------------------
 * 读的端点 / 写的端点
 * ---------------------------------------------------------------------------
 *  - `GET  /api/students/{id}/home?as_of=` · **学生头** —— 只为拿 `semester_id` 与 `week`
 *    （完成率端点的两个**必填**查询参数在别处读不到）；
 *  - `GET  /api/students/{id}/training-logs/completion-rate?semester_id=&week=` · **学生头**；
 *  - `GET  /api/students/{id}/weekly-sheet?as_of=` · **学生头** —— 这一周哪几天是训练日、
 *    各自的重点是什么（打卡表单的日期快选按它铺）；
 *  - `GET  /api/training-logs`（匿名泛型 list，**翻页收集 + 客户端按 `student_id` 过滤**，
 *    见 `endpoints.ts` 的 `listMyTrainingLogs`）—— 已打卡的那几天要标出来，
 *    否则用户点了提交才吃一个 409；
 *  - `POST /api/training-logs` · **学生头** · 201。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ 请求体只有 5 个键（派单逐字要求的那一格）
 * ---------------------------------------------------------------------------
 * `TrainingLogCreate` 实测的 `required` 是 `["log_date", "completed"]`，全部键是
 * `log_date / completed / duration_min / feeling / is_rest_day`。
 * **`student_id` 来自请求头，`submitted_at` / `late` / `source` / `batch_id`
 * 四个一律由服务端填**（`feedback.py:671-709`：`late` 的判定式是
 * `submitted_at.time() > CHECKIN_DEADLINE`，即 22:00 之后提交）。
 * 前端传了也**没用**（Pydantic 会把 `TrainingLogCreate` 里没声明的键丢掉），
 * 而「以为传了就生效」的失效形态是**完成率被前端伪造** —— 那是 RCT 的关键过程指标。
 *
 * ⚠️ `feeling` 的值域 = `easy` / `moderate` / `hard`（`TrainingLog.FEELINGS`，DB 上有 CHECK），
 *    中文标签「轻松 / 适中 / 吃力」由前端映射（`present.ts` 是那一格的所有者）。
 * ⚠️ 同一天重复提交 → **409 `integrity_conflict`**（`uq_training_log_student_day`）。
 *    后端**刻意不做**「补卡覆盖旧行」：一天一行是这张表的口径。
 */
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ApiError } from '../../api/client'
import {
  createTrainingLog,
  getCompletionRate,
  getStudentHome,
  getWeeklySheet,
  listMyTrainingLogs,
} from '../../api/endpoints'
import type { components } from '../../api/generated/schema'
import type { TrainingLogListItem } from '../../api/types'
import { useApiError } from '../../components/ApiErrorBanner.vue'
import SectionHead from '../../components/SectionHead.vue'
import SuccessMark from '../../components/SuccessMark.vue'
import StatBlock from '../../components/StatBlock.vue'
import StudentNav from '../../components/StudentNav.vue'
import { useAsync } from '../../composables/useAsync'
import { useFormValidity } from '../../composables/useFormValidity'
import { useIdentityStore } from '../../stores/identity'
import {
  FEELINGS,
  UNKNOWN,
  feelingZh,
  mondayOf,
  num,
  shortDate,
  stampOf,
  toPercent,
  weekdayOf,
} from '../../present'

type Rate = components['schemas']['CompletionRateRead']
type Sheet = components['schemas']['WeeklySheetRead']

const identity = useIdentityStore()
const route = useRoute()

/** `?date=YYYY-MM-DD` 的深链接（首页的待办条目带它过来）。不合格就退回业务日。 */
function initialDate(): string {
  const raw = route.query.date
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : identity.asOf
}

const { data, loading, settled, reload } = useAsync(async () => {
  const id = identity.studentId
  if (id === null) return null
  const home = await getStudentHome(id, { asOf: identity.asOf })
  const [rate, sheet, logs] = await Promise.all([
    home.semester_id !== null && home.week !== null
      ? getCompletionRate(id, { semesterId: home.semester_id, week: home.week }).catch(
          (err: unknown) => (err instanceof ApiError ? err : null),
        )
      : Promise.resolve(null),
    getWeeklySheet(id, { asOf: identity.asOf }).catch((err: unknown) =>
      err instanceof ApiError ? err : null,
    ),
    listMyTrainingLogs(id).catch(() => ({ items: [], truncated: false })),
  ])
  return { home, rate, sheet, logs }
})

watch([() => identity.studentId, () => identity.asOf], () => void reload())

/* ------------------------------------------------------------- 读出来的几格 */
const rate = computed<Rate | ApiError | null>(() => data.value?.rate ?? null)
const rateValue = computed<Rate | null>(() =>
  rate.value instanceof ApiError ? null : rate.value,
)
const sheet = computed<Sheet | ApiError | null>(() => data.value?.sheet ?? null)
const sheetValue = computed<Sheet | null>(() =>
  sheet.value instanceof ApiError ? null : sheet.value,
)
const logs = computed<TrainingLogListItem[]>(() => data.value?.logs.items ?? [])
const truncated = computed(() => data.value?.logs.truncated ?? false)

const monday = computed(() => mondayOf(identity.asOf))

/** 我的日志按日期倒序（后端给的序不保证，故显式排）。 */
const myLogs = computed(() =>
  [...logs.value].sort((a, b) => b.log_date.localeCompare(a.log_date)),
)

const logByDate = computed(() => new Map(myLogs.value.map((row) => [row.log_date, row])))

/** 这一周的应打卡日（来自完成率端点的 `expected_days`，它是后端算好的口径）。 */
const expectedDays = computed(() => rateValue.value?.expected_days ?? [])
const completedDays = computed(() => new Set(rateValue.value?.completed_days ?? []))

/* ------------------------------------------------------------- 表单 */
const logDate = ref(initialDate())
const completed = ref(true)
/** ⚠️⚠️ **`string | number`，不是 `string`**（Plan 07 Task 5b 缺陷 ① 的**第三格**，
 *  本波实测出来的、比派单点的那一格更靠上游的一个）。
 *
 *  Vue 的 `vModelText`（`@vue/runtime-dom`）对 `<input type="number">` **在运行时把值
 *  转成 number**：`castToNumber = number || vnode.props.type === 'number'`，
 *  于是 `domValue = looseToNumber(el.value)`。故用户**手输**之后这一格是 `30.9`
 *  （number）而不是 `'30.9'`（string）；空的时候是 `''`（`parseFloat('')` 是 NaN，
 *  `looseToNumber` 原样返回）。⚠️ 而下面那个预填 `watch` 写的是 `String(…)`，
 *  故「预填」与「手输」两条路给这一格的**类型不同**。
 *
 *  ⚠️ 改前它声明成 `ref('')`（= `Ref<string>`）而 `submit()` 里直接
 *  `durationText.value.trim()` ⇒ **手输任何数字都当场**
 *  `TypeError: durationText.value.trim is not a function`（2026-10-15 CDP 实测原文：
 *  `[unhandled] native event handler TypeError: durationText.value.trim is not a function
 *  at submit (…/CheckIn.vue:157:40)`）。⚠️ 而它抛在 `submitting.value = true` **之后**、
 *  `try` **之前** ⇒ `finally` 那一格不跑 ⇒ 按钮**永久**停在「正在提交…」且 disabled，
 *  **一个请求都没发出去**，页面上一个字都没多（要恢复只能刷新页面）。
 *  即：那一格的占位符逐字写着「例如 35」，而**照着它做就必中**。
 *
 *  ⚠️ 它此前一直没被发现，是因为**同一个输入框上还有第二个静默**：`step="0.5"`
 *  与库里那一位小数的预填值撞车 ⇒ 原生校验先把 submit 拦下来，`submit()` 根本跑不到
 *  那一行。把 `step` 改对之后它才露出来（本波逐格实测的顺序也正是这样）。
 *  ⚠️ 而「类型声明与运行时不一致」这一档 `vue-tsc` **一句话都不说**（模板里的
 *  `v-model` 赋值方向不做那一格检查）—— 这就是本仓「不要靠读代码推断行为、
 *  跑起来量」（硬规矩 #89/#103）的又一格。 */
const durationText = ref<string | number>('')
const feeling = ref<'easy' | 'moderate' | 'hard' | null>(null)
const isRestDay = ref(false)
const submitting = ref(false)
const stamp = ref(false)
const stampCaption = ref('')
const submitError = ref<ApiError | null>(null)
const lastCreated = ref<components['schemas']['TrainingLogRead'] | null>(null)

/** ⚠️ **Plan 07 Task 5b 缺陷 ① 的病灶那一半**：原生校验拦下一次提交时，
 *  用户必须看得见一句人话。住址（判据与措辞的单一所有者）是
 *  `composables/useFormValidity.ts`；本处只负责把它画出来。
 *  ⚠️ `clear` 那一格是**真的会用到的**：下面那个预填 `watch` 改的是 ref
 *  （Vue 直接写 `input.value`，**不**触发 `input` 事件），故换一天时
 *  上一次那句「这一格没通过校验」不会自己消失 —— 不手动清掉就是一句过期话。 */
const { notice: formNotice, bind: bindForm, clear: clearFormNotice } = useFormValidity()

/** 已经打过卡的那一天：提交前就挡掉，而不是让用户吃一个 409。 */
const alreadyLogged = computed(() => logByDate.value.has(logDate.value))

const pickedIsTrainingDay = computed(() => expectedDays.value.includes(logDate.value))

/** 选中的那一天在训练单上练什么（`day` 1 = 周一，故用与 `monday` 的差算）。
 *  ⚠️ 训练单读不到（两档 404）时它是 `null`，模板据此显示「这一天不在训练单上」。 */
const pickedFocus = computed(() => {
  const s = sheetValue.value
  if (!s) return null
  const a = Date.parse(`${monday.value}T00:00:00Z`)
  const b = Date.parse(`${logDate.value}T00:00:00Z`)
  if (Number.isNaN(a) || Number.isNaN(b)) return null
  const day = Math.round((b - a) / 86_400_000) + 1
  const session = s.sessions.find((x) => x.day === day)
  return session ? { day, focus: session.focus, blocks: session.blocks.length } : null
})

/**
 * ⚠️ 两个依赖一起看：`expectedDays` 是**异步**到的（首帧是空数组），
 * 只 watch `logDate` 的话「业务日不是训练日 → 自动勾上休息日」这一格永远不会发生
 * （spec §8.1 逐字：「每日都可打卡，非训练日一键『今日休息』」）。
 */
watch([logDate, expectedDays], ([next]) => {
  isRestDay.value = !expectedDays.value.includes(next)
  // ⚠️ 换一天 ⇒ 下面那一格会被重新预填，故上一次那句「没通过校验」已经过期。
  clearFormNotice()
  const existing = logByDate.value.get(next)
  if (existing) {
    completed.value = existing.completed
    durationText.value = existing.duration_min === null ? '' : String(existing.duration_min)
    feeling.value =
      existing.feeling === 'easy' || existing.feeling === 'moderate' || existing.feeling === 'hard'
        ? existing.feeling
        : null
  }
})

function pickFeeling(value: 'easy' | 'moderate' | 'hard'): void {
  feeling.value = feeling.value === value ? null : value
}

async function submit(): Promise<void> {
  if (identity.studentId === null || submitting.value) return
  submitting.value = true
  submitError.value = null
  stamp.value = false
  // ⚠️ `String(…)` 是承重的，理由逐字写在 `durationText` 那个 ref 的注释里
  //    （`type="number"` 的 v-model 在运行时给的是 number，`.trim()` 会当场抛）。
  const duration = String(durationText.value).trim()
  // ⚠️ 这五个键就是 `TrainingLogCreate` 的全部：`submitted_at` / `late` /
  //    `student_id` / `source` / `batch_id` **一个都不传**（见文件顶部）。
  const body: components['schemas']['TrainingLogCreate'] = {
    log_date: logDate.value,
    completed: completed.value,
    duration_min: completed.value && duration !== '' ? Number(duration) : null,
    feeling: completed.value ? feeling.value : null,
    is_rest_day: isRestDay.value,
  }
  try {
    const created = await createTrainingLog(body)
    lastCreated.value = created
    stampCaption.value = `${created.log_date} · ${created.late ? '迟交（22:00 后）' : '按时'} · 服务端记于 ${stampOf(created.submitted_at)}`
    stamp.value = true
    durationText.value = ''
    await reload()
  } catch (err) {
    if (!(err instanceof ApiError)) {
      console.error('[check-in] 提交时出了非 ApiError 的异常', err)
      return
    }
    submitError.value = err
    // ⚠️ 409 那一档**不**送进红色横幅：它是「你已经打过了」，是页面内容；
    //    横幅会让人以为系统坏了。其余各档照常送横幅（那里有按 code 的处置建议）。
    if (err.code !== 'integrity_conflict') useApiError().raise(err)
  } finally {
    submitting.value = false
  }
}

/** 409 那一档的人话（派单要求「各给一句人话」）。 */
const submitAdvice = computed(() => {
  const err = submitError.value
  if (!err) return ''
  if (err.code === 'integrity_conflict') {
    return `这一天（${logDate.value}）你已经打过卡了：一天只能有一行，后端刻意不做「补卡覆盖旧行」——那样会让「他当时交的是什么」在库里查不到。要改口径请让教师在管理台里查那一行。`
  }
  if (err.code === 'unprocessable_value' || err.code === 'request_validation_failed') {
    return '提交的值没通过校验。⚠️ 检查 `duration_min` 是不是一个 ≥ 0 的数、`log_date` 是不是 `YYYY-MM-DD`。'
  }
  if (err.code === 'unauthenticated' || err.code === 'forbidden') {
    // ⚠️ 改前逐字是「身份不对：本端点要 `X-Student-Id`，且它必须与要写的那一行是
    //    同一个人。」—— Plan 05A 之后那是一句**假话**：身份的唯一载体是
    //    `pe_session` cookie，而 `X-Student-Id` 那条通道只在**开发档构建**且后端
    //    显式设 `PE_ALLOW_HEADER_IDENTITY=1` 时存在（交付的三个脚本一律强制清掉它，
    //    `prod` 档下 `app.api.deps.allow_header_identity()` 结构上恒 False）。
    return '会话不对：这一格要**学生本人**的会话（`pe_session` cookie），而写进去那一行的 `student_id` 由服务端从会话取。会话过期或换过身份，请在上面的会话条上登出再登录。'
  }
  return ''
})
</script>

<template>
  <div class="s-page">
    <StudentNav />

    <div v-if="identity.studentId === null" class="s-empty">
      <p class="s-empty__title zh-title">还不知道你是谁</p>
      <p class="s-empty__note">
        打卡是<strong>写</strong>操作：<code>POST /api/training-logs</code> 要
        <strong>学生本人</strong>的会话（<code>pe_session</code> cookie），而写进去那一行的
        <code>student_id</code> 由服务端<strong>从会话</strong>取（请求体里**没有**
        <code>student_id</code>，故没法替别人打卡）。请在上面的会话条上登出、
        再用一个学生账号登录。
      </p>
    </div>

    <div v-else-if="loading && !settled" class="s-loading">
      <span class="s-loading__rule" aria-hidden="true"></span>
      <span>正在读这一周的应打卡日…</span>
    </div>

    <template v-else-if="data">
      <header class="s-head">
        <p class="caps s-head__kicker">
          DAILY LOG · 学期第 {{ num(data.home.week) }} 周 · {{ identity.asOf }}
        </p>
        <h2 class="zh-title s-head__title">每日打卡</h2>
        <p class="s-head__meta">
          提交时刻与「是否迟交」都由服务端算 —— 前端传不了，也改不了。
        </p>
      </header>

      <!-- 01 · 完成率 -->
      <section class="s-card">
        <SectionHead :index="1" label="COMPLETION" />
        <div class="s-subhead">
          <span class="s-subhead__title">
            学期第 {{ num(data.home.week) }} 周 /
            <template v-if="rateValue">处方第 {{ num(rateValue.prescription_week) }} 周</template>
            <template v-else>处方周次未知</template>
          </span>
          <span class="s-subhead__aside">
            {{ rateValue ? `${rateValue.numerator} / ${rateValue.denominator}` : UNKNOWN }}
          </span>
        </div>

        <StatBlock
          :value="toPercent(rateValue?.completion_rate ?? null)"
          :decimals="1"
          unit="%"
          label="本周打卡完成率"
          size="hero"
          :level="
            rateValue && rateValue.completion_rate !== null
              ? rateValue.completion_rate >= 1
                ? 'moss'
                : rateValue.completion_rate >= 0.6
                  ? 'amber'
                  : 'red'
              : 'default'
          "
        />

        <!-- ⚠️ 约束第 10 条：null → 「—」+ 后端那句 reason（三档各不相同，
             `feedback.py:761-768` 逐字「三档的 reason 各不相同，故前端能给三种提示」）。 -->
        <div v-if="rateValue && rateValue.completion_rate === null" class="s-unknown">
          <p class="s-unknown__title zh-title">完成率没有定义（不是 0%）</p>
          <p class="s-unknown__note">{{ rateValue.reason ?? '后端没有给理由。' }}</p>
        </div>
        <div v-else-if="rate instanceof ApiError" class="s-notice s-notice--warn">
          <p class="s-notice__title">{{ rate.code }} · {{ rate.status }}</p>
          <p>{{ rate.message }}</p>
        </div>
        <p v-else-if="rateValue && rateValue.paused" class="s-notice s-notice--warn">
          <span class="s-notice__title">本周训练单已暂停</span>
          暂停期间仍然可以打卡（休息日打卡），但它不计入完成率。
        </p>

        <div v-if="expectedDays.length > 0" class="days">
          <span
            v-for="day in expectedDays"
            :key="day"
            class="days__chip"
            :class="{ 'days__chip--done': completedDays.has(day) }"
          >
            <span class="days__wd caps">{{ weekdayOf(day).slice(1) }}</span>
            <span class="days__d num">{{ day.slice(5) }}</span>
            <span class="days__s">{{ completedDays.has(day) ? '已计入' : '未计入' }}</span>
          </span>
        </div>
        <p class="s-block__note">
          口径：分母只数<strong>处方训练日 ∩ 这一周的 7 天</strong>；补卡（提交日与训练日不同）、
          迟交（22:00 之后）与休息日打卡都<strong>不计入</strong>分子。
          故「库里有那一行」与「计入完成率」是两件事。
        </p>
      </section>

      <!-- 02 · 打卡表单 -->
      <section class="s-card">
        <SectionHead :index="2" label="SUBMIT" />
        <div class="s-subhead">
          <span class="s-subhead__title">交一次卡</span>
          <span class="s-subhead__aside">
            <template v-if="pickedFocus">
              训练单第 {{ pickedFocus.day }} 天 · {{ pickedFocus.focus }} ·
              {{ pickedFocus.blocks }} 个动作
            </template>
            <template v-else>这一天不在本周训练单上</template>
          </span>
        </div>

        <!-- ⚠️ `:ref="bindForm"` 是 Plan 07 Task 5b 加的：它把这张表单接到
             `composables/useFormValidity.ts` 上，于是「原生校验拦下 submit」那一档
             不再是静默的（改前实测：点了「提交打卡」之后一个请求都没发、
             页面上一个字都没多）。⚠️ 它**不改**任何既有行为：`@submit.prevent`
             仍然只在**校验通过**时触发。 -->
        <form :ref="bindForm" class="form" @submit.prevent="submit">
          <label class="field">
            <span class="field__label">训练日 log_date</span>
            <input v-model="logDate" class="input" type="date" name="log_date" required />
          </label>

          <div class="quick">
            <button
              v-for="day in expectedDays"
              :key="day"
              type="button"
              class="quick__btn"
              :class="{ 'quick__btn--on': logDate === day }"
              @click="logDate = day"
            >
              {{ shortDate(day) }} {{ weekdayOf(day) }}
            </button>
            <button
              type="button"
              class="quick__btn"
              :class="{ 'quick__btn--on': logDate === identity.asOf }"
              @click="logDate = identity.asOf"
            >
              业务日 {{ identity.asOf }}
            </button>
          </div>

          <div class="field">
            <span class="field__label">今天练了吗 completed</span>
            <div class="toggle">
              <button
                type="button"
                class="toggle__btn"
                :class="{ 'toggle__btn--on': completed }"
                @click="completed = true"
              >
                练了
              </button>
              <button
                type="button"
                class="toggle__btn"
                :class="{ 'toggle__btn--on': !completed }"
                @click="completed = false"
              >
                没练
              </button>
            </div>
          </div>

          <template v-if="completed">
            <label class="field">
              <span class="field__label">练了多少分钟 duration_min（可留空）</span>
              <!-- ⚠️⚠️ `step="any"`（Plan 07 Task 5b 缺陷 ①）。**改前是 `step="0.5"`，
                   那是前端自己发明的一个口径，没有任何人拥有它。**
                   `duration_min` 的口径所有者是后端
                   `app/api/schemas/feedback.py` 的
                   `TrainingLogCreate.duration_min: float | None = Field(default=None, ge=0)`
                   —— 只有一个下界 `ge=0`（就是下面那个 `min="0"`），**没有** `multiple_of`。
                   三格实测取证（2026-10-15，打本波自己起的 8000，⚠️ 不是甲方那份 8030）：
                     · openapi 上它逐字是
                       `anyOf: [{"type":"number","minimum":0.0},{"type":"null"}]`，
                       而 `TrainingLogCreate` 五个属性里 `multipleOf` 一个都没有；
                     · 实发请求：30.9 → **201**、30.95 → **201**、1e6 → **201**、
                       -1 → **422** `greater_than_equal`（`loc = ["body","duration_min"]`）；
                     · 库里 840 行 `training_log`：`duration_min` 非空 628 行，
                       小数位数是「1 位 565 行 / 0 位 63 行」，327 个 distinct 值里
                       **258 个不是 0.5 的整数倍**（生成式是 `app/demo_data.py` 的
                       `round(uniform(20.0, 60.0), 1)`）。
                   ⚠️ 于是「口径是 0.5 分钟一档」这句话在**后端、DB、spec §8.1 三处都
                   找不到住址**（spec 那一格逐字只有「完成时长（分钟）」），而仿真数据
                   是一位小数 ⇒ 撞的是**前端**，不是数据。⚠️ 而数据那一侧**一个字都不许改**
                   （它是 13 个波次的取证基础）。
                   ⚠️ 取 `any` 而**不是** `0.1`：`any` 逐字等于后端那个口径（「任意 ≥ 0 的
                   实数」），而 `0.1` 又是一个前端自己发明的新口径、只是今天恰好不撞 ——
                   明天来一个两位小数的数据源，同一个静默就回来了。
                   ⚠️ 而往松的那一侧靠是**安全**的：真有个后端不认的值，`any` 放行 ⇒
                   后端回 422 ⇒ `ApiErrorBanner` 把 `loc` 与原因都画出来。
                   「太松会响、太紧会哑」⇒ 一律取松的那一侧。
                   ⚠️ 失效方向那一半（拦下 submit 时不许静默）由上面那个 `:ref="bindForm"`
                   与 `composables/useFormValidity.ts` 兜住，两件事**都做了**。
                   ⚠️ `inputmode="decimal"` 保留：手机上仍然弹数字键盘。 -->
              <input
                v-model="durationText"
                class="input"
                type="number"
                name="duration_min"
                min="0"
                step="any"
                inputmode="decimal"
                placeholder="例如 35"
              />
            </label>

            <div class="field">
              <span class="field__label">自评感受 feeling（可留空）</span>
              <div class="feel">
                <button
                  v-for="option in FEELINGS"
                  :key="option.value"
                  type="button"
                  class="feel__btn"
                  :class="{ 'feel__btn--on': feeling === option.value }"
                  @click="pickFeeling(option.value)"
                >
                  <span class="feel__zh zh-title">{{ option.zh }}</span>
                  <span class="feel__caps caps">{{ option.caps }}</span>
                  <span class="feel__hint">{{ option.hint }}</span>
                </button>
              </div>
            </div>
          </template>

          <label class="check">
            <input v-model="isRestDay" type="checkbox" name="is_rest_day" />
            <span>
              今天是<strong>休息日</strong>（<code>is_rest_day</code>）——
              <template v-if="pickedIsTrainingDay">
                ⚠️ 但这一天是<strong>处方训练日</strong>，勾上它就不会计入完成率。
              </template>
              <template v-else>
                这一天不是处方训练日，勾上它就是 spec §8.1 的「一键『今日休息』」。
              </template>
            </span>
          </label>

          <div v-if="alreadyLogged" class="s-notice s-notice--warn">
            <p class="s-notice__title">这一天已经有一行了</p>
            <p>
              库里已经有 <code>{{ logDate }}</code> 的打卡记录
              （<code>{{ completedDays.has(logDate) ? '已计入完成率' : '未计入完成率' }}</code>）。
              再提交会得到 <strong>409 <code>integrity_conflict</code></strong>
              —— 一天一行是这张表的口径，后端刻意不做覆盖。
            </p>
          </div>

          <!-- ⚠️ 原生校验拦下提交时的**那一句人话**（Plan 07 Task 5b 缺陷 ① 的病灶）。
               措辞与判据的住址是 `composables/useFormValidity.ts`（单一所有者），
               本处只用**本页既有的**错误态类把它画出来（`.s-notice .s-notice--warn`，
               与下面「这一天已经有一行了」那一块同一族）⇒ **一行新 CSS 都没加**，
               `npm run check:tokens` 一格都不退。
               ⚠️ 它排在提交按钮**上面**：点完按钮之后用户的视线就在那里，
               而浏览器那个原生气泡在 headless 取证里读不到、在真浏览器上也是一闪就没。 -->
          <div v-if="formNotice" class="s-notice s-notice--warn" role="alert">
            <p class="s-notice__title">{{ formNotice.title }}</p>
            <p>{{ formNotice.body }}</p>
          </div>

          <div class="s-actions">
            <button class="btn btn--primary" type="submit" :disabled="submitting">
              {{ submitting ? '正在提交…' : '提交打卡' }}
            </button>
            <span class="form__note">
              只会发出 5 个键：<code>log_date / completed / duration_min / feeling / is_rest_day</code>
            </span>
          </div>
        </form>

        <!-- 成功反馈：只在「一次真的写进了库」时出现（计划 §3 动效②：200ms 对勾淡入） -->
        <SuccessMark
          :visible="stamp"
          text="已打卡"
          :caption="stampCaption"
          tone="moss"
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
            <span class="s-row__key">服务端算的 late</span>
            <span class="s-row__val">{{ lastCreated.late ? '是（22:00 之后提交）' : '否' }}</span>
          </div>
          <div class="s-row">
            <span class="s-row__key">source / batch_id</span>
            <span class="s-row__val">
              {{ lastCreated.source }} /
              <!-- ⚠️ `batch_id` 恒为 null（`feedback.py:683-684`：这一行不属于任何批次，
                   而 NULL 让它天然躲过「重放那天先删后算」）→ 显示「—」，不是 0。 -->
              <template v-if="lastCreated.batch_id === null"><span class="unknown">{{ UNKNOWN }}</span>（不属于任何批次）</template>
              <template v-else>{{ lastCreated.batch_id }}</template>
            </span>
          </div>
        </div>
      </section>

      <!-- 03 · 我的打卡记录 -->
      <section class="s-card">
        <SectionHead :index="3" label="HISTORY" />
        <div class="s-subhead">
          <span class="s-subhead__title">我的打卡记录</span>
          <span class="s-subhead__aside">{{ myLogs.length }} 行</span>
        </div>

        <div v-if="myLogs.length === 0" class="s-empty">
          <svg class="s-empty__mark" viewBox="0 0 88 20" aria-hidden="true">
            <path class="s-empty__mark-line" d="M2 6 H86" />
            <path class="s-empty__mark-hair" d="M2 14 H40" />
          </svg>
          <p class="s-empty__title zh-title">还没有打卡记录</p>
          <p class="s-empty__note">
            ⚠️ 这一格与「完成率未知」是两件事：这里说的是
            <code>training_log</code> 表里<strong>一行都没有</strong>（上面那格说的是
            有行、但完成率没有定义）。交一次卡就有了。
          </p>
        </div>

        <table v-else class="data-table hist">
          <thead>
            <tr>
              <th scope="col">日期</th>
              <th scope="col">练了</th>
              <th scope="col">分钟</th>
              <th scope="col">感受</th>
              <th scope="col">标记</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in myLogs.slice(0, 21)" :key="row.id">
              <td>
                {{ row.log_date }}
                <span class="hist__wd">{{ weekdayOf(row.log_date) }}</span>
              </td>
              <td>{{ row.completed ? '是' : '否' }}</td>
              <!-- ⚠️ `duration_min` 可空（「没练就没有时长」）→ 「—」，不是 0 -->
              <td>{{ num(row.duration_min, 1) }}</td>
              <td>{{ feelingZh(row.feeling) }}</td>
              <td class="hist__flags">
                <span v-if="row.late" class="pill pill--red">迟交</span>
                <span v-if="row.is_rest_day" class="pill pill--amber">休息日</span>
                <span class="hist__src data">{{ row.source }}</span>
              </td>
            </tr>
          </tbody>
        </table>

        <p v-if="truncated" class="s-block__note">
          ⚠️ 只收到前 {{ myLogs.length }} 行（收集上限）：泛型 list 没有按学生过滤的参数，
          翻页收集到上限就停了。
        </p>
        <p v-else class="s-block__note">
          最近 {{ Math.min(myLogs.length, 21) }} 行（共 {{ myLogs.length }} 行）。
          <code>source</code> 的 <code>demo</code> 是演示库灌的，
          <code>student</code> 才是从本页交上去的。
        </p>
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

/* 日期快选：一排小芯片，375px 下允许换行（不做横向滚动 —— 滚出视野的按钮等于不存在） */
.quick {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.quick__btn {
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-raise);
  font-family: var(--font-data);
  font-size: var(--fs-micro);
  font-variant-numeric: tabular-nums;
  color: var(--ink-soft);
}

.quick__btn--on {
  border-color: var(--primary);
  background: var(--primary);
  color: var(--on-primary);
}

.toggle {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
}

.toggle__btn {
  padding: var(--space-3);
  border: 2px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-raise);
  font-family: var(--font-ui);
  font-weight: var(--fw-700);
  font-size: var(--fs-body);
  color: var(--ink-soft);
}

.toggle__btn--on {
  border-color: var(--primary);
  background: var(--primary);
  color: var(--on-primary);
}

/* 三个感受按钮：等宽一行，每个都过了 44px 的触控下限 */
.feel {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-2);
}

.feel__btn {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  min-height: 62px;
  padding: var(--space-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-raise);
  text-align: left;
}

.feel__btn--on {
  border-color: var(--primary);
  border-width: 2px;
  background: var(--surface-raise);
  box-shadow: inset 0 calc(-1 * var(--bar-accent)) 0 var(--primary);
}

.feel__zh {
  font-size: var(--fs-body);
  font-weight: var(--fw-700);
}

.feel__caps {
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.feel__hint {
  font-size: 10px;
  line-height: 1.3;
  color: var(--ink-soft);
}

.check {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  font-size: var(--fs-small);
  color: var(--ink-soft);
}

.check input {
  inline-size: 18px;
  block-size: 18px;
  accent-color: var(--primary);
  flex: 0 0 auto;
}

/* ------------------------------------------------------------- 完成率那排日期 */
.days {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.days__chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
  min-width: 56px;
  padding: var(--space-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-raise);
}

.days__chip--done {
  border-color: var(--green);
  background: var(--green-faint);
}

.days__wd {
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.days__d {
  font-family: var(--font-ui);
  font-weight: var(--fw-600);
  font-size: var(--fs-small);
  font-variant-numeric: tabular-nums;
}

.days__s {
  font-size: var(--fs-micro);
  color: var(--ink-soft);
}

.days__chip--done .days__s {
  color: var(--green);
}

/* ------------------------------------------------------------- 历史表 */
.hist {
  font-size: var(--fs-micro);
}

.hist td,
.hist th {
  padding-inline-end: var(--space-1);
}

.hist__wd {
  color: var(--ink-faint);
  font-family: var(--font-ui);
  font-size: var(--fs-micro);
}

.hist__flags {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  align-items: center;
}

.hist__src {
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}
</style>
