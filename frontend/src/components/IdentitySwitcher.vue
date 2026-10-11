<script setup lang="ts">
/**
 * `IdentitySwitcher.vue` —— **代替登录页**（计划非目标第 1 条 / Task 1 第 9 步）。
 *
 * ---------------------------------------------------------------------------
 * 为什么会有它
 * ---------------------------------------------------------------------------
 * 本系统不做真实登录/鉴权。身份走两个请求头（`X-Student-Id` /
 * `X-Teacher-Staff-No`），它们是后端 OpenAPI 的两个 `apiKey` securityScheme
 * （实测 `/openapi.json` 的 `components.securitySchemes` 键集合逐字就是这两个）。
 * 原型口径逐字是「挡事故、不挡攻击」（`app/api/deps.py:3-7`）。
 * 故这里做一件事：**把「我是谁」变成一个可以随手换的下拉框**，
 * 换完之后 `client.ts` 就自动带上对应的那一个头。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 三个实测口径（不是抄计划的）
 * ---------------------------------------------------------------------------
 * 1. **名单从后端拉，不硬编码**：`GET /api/students?limit=200` 与
 *    `GET /api/teachers?limit=200`。两个都是**匿名** GET（47 个 GET 全部匿名，
 *    约束第 3 条），故**没选身份也能拉到名单** —— 这正是「先有鸡」那一档的解法。
 *    ⚠️ `limit` 的上界是 **200**（`deps.Page`，实测 openapi 里 `maximum: 200`），
 *    故超过 200 个学生时这个下拉框会缺人；演示库实测是 **60 学生 / 3 教师**，够用。
 *    真的缺了会在下面显示一行提示，不会静默。
 * 2. **`as_of` 的缺省是 `2025-10-12`**，即**演示库的业务日**（学期第 6 周的周日），
 *    **不是「今天」**。用今天当查询日期会查不到任何数据（约束第 22 条）。
 *    唯一所有者是 `stores/identity.ts` 的 `DEMO_AS_OF`。
 * 3. **一次只有一种身份生效**：选了学生就清掉教师，反之亦然。
 *    `client.ts` 因此只注入一个头（理由见那里的注释：两个头都发会让
 *    「这一行是谁写的」变成要读两个地方才能回答的事）。
 */
import { computed, onMounted, ref } from 'vue'

import { ApiError } from '../api/client'
import { listStudents, listTeachers } from '../api/endpoints'
import type { StudentListItem, TeacherListItem } from '../api/types'
import { DEMO_AS_OF, useIdentityStore } from '../stores/identity'
import { useApiError } from './ApiErrorBanner.vue'
import LaneDivider from './LaneDivider.vue'

/** `limit` 的上界。⚠️ 与后端 `deps.Page` 的 `Query(ge=1, le=200)` 同源；
 *  Task 5 的联调脚本要把它与 `/openapi.json` 对拍一次。 */
const ROSTER_LIMIT = 200

const identity = useIdentityStore()
const { raise } = useApiError()

const students = ref<StudentListItem[]>([])
const teachers = ref<TeacherListItem[]>([])
const studentTotal = ref<number | null>(null)
const teacherTotal = ref<number | null>(null)
const loading = ref(false)
/** 拉名单失败时的一句本地提示。⚠️ 它**不**替代横幅：横幅说「后端怎么了」，
 *  这一句说「所以这个下拉框现在是空的」—— 用户看的是下拉框。 */
const loadFailure = ref('')

/** 当前选中的角色。⚠️ 写成 computed 的 getter/setter，于是三个单选按钮
 *  与 store 只有一个数据源（store），不存在「按钮显示学生、store 里是教师」那一档。 */
const role = computed<'student' | 'teacher' | 'none'>({
  get: () => identity.role ?? 'none',
  set: (next) => {
    if (next === 'none') identity.clearIdentity()
    else if (next === 'student') pickStudent(identity.studentId ?? students.value[0]?.id ?? null)
    else pickTeacher(identity.teacherStaffNo ?? teachers.value[0]?.staff_no ?? null)
  },
})

const asOf = computed({
  get: () => identity.asOf,
  set: (next: string) => identity.setAsOf(next),
})

/** 业务日是不是演示库的那一天。⚠️ 不是就提醒：那是「查不到数据」最常见的原因。 */
const asOfIsDemoDay = computed(() => identity.asOf === DEMO_AS_OF)

/** `<select>` 的 `change` 事件 → 学生 id。⚠️ 空串/NaN 一律当「没选」，
 *  于是那个 `disabled` 的占位 `<option>` 不会把身份清成一个 `NaN`。 */
function onPickStudent(event: Event): void {
  const raw = (event.target as HTMLSelectElement).value
  const parsed = Number(raw)
  pickStudent(raw === '' || Number.isNaN(parsed) ? null : parsed)
}

function onPickTeacher(event: Event): void {
  const raw = (event.target as HTMLSelectElement).value
  pickTeacher(raw === '' ? null : raw)
}

function pickStudent(studentId: number | null): void {
  if (studentId === null) return
  const found = students.value.find((s) => s.id === studentId)
  identity.becomeStudent(
    studentId,
    found ? `${found.student_no} ${found.name}` : identity.studentLabel,
  )
}

function pickTeacher(staffNo: string | null): void {
  if (staffNo === null) return
  const found = teachers.value.find((t) => t.staff_no === staffNo)
  identity.becomeTeacher(staffNo, found ? found.name : identity.teacherLabel)
}

async function loadRosters(): Promise<void> {
  loading.value = true
  loadFailure.value = ''
  try {
    // ⚠️ 两个请求并发（`Promise.all`）：它们互不依赖，串行等于把首屏的
    //    一次 RTT 变成两次。
    const [studentPage, teacherPage] = await Promise.all([
      listStudents({ limit: ROSTER_LIMIT }),
      listTeachers({ limit: ROSTER_LIMIT }),
    ])
    students.value = studentPage.items
    teachers.value = teacherPage.items
    studentTotal.value = studentPage.total
    teacherTotal.value = teacherPage.total

    // ⚠️ 名单到了之后，把 store 里**持久化的那一个身份**回填上它的显示名。
    //    localStorage 存了 label，但存的那一份可能是上一次演示库的名字
    //    （库被重灌过）；以刚拉到的名单为准。
    if (identity.role === 'student' && identity.studentId !== null) {
      pickStudent(identity.studentId)
    } else if (identity.role === 'teacher' && identity.teacherStaffNo !== null) {
      pickTeacher(identity.teacherStaffNo)
    }
  } catch (err) {
    // ⚠️ 两件事都做：横幅说清后端那一档，本地这一句说清下拉框为什么是空的。
    loadFailure.value =
      err instanceof ApiError
        ? `名单没拉到（${err.code}）：后端没起，或者代理没通。下面两个下拉框是空的。`
        : '名单没拉到（不是后端回的错误，看浏览器控制台）。下面两个下拉框是空的。'
    if (err instanceof ApiError) raise(err)
  } finally {
    loading.value = false
  }
}

/** 超过 `limit` 上界时提示缺人。⚠️ 不静默：一个少了人的下拉框会让人以为
 *  「这个学生不存在」，而那是 403 `forbidden` 的症状之一 —— 两种原因要能分开。 */
const studentTruncated = computed(
  () => studentTotal.value !== null && studentTotal.value > students.value.length,
)
const teacherTruncated = computed(
  () => teacherTotal.value !== null && teacherTotal.value > teachers.value.length,
)

onMounted(loadRosters)
</script>

<template>
  <section class="switcher" aria-label="身份切换器">
    <LaneDivider :index="1" label="IDENTITY" />

    <div class="switcher__row">
      <!-- 角色：三个单选按钮。⚠️ 用 radio 而不是 select —— 「我是谁」是本原型
           最高频的一次操作，一次点击要比两次点击（展开 + 选）好。 -->
      <fieldset class="switcher__roles">
        <legend class="caps">我是</legend>
        <label class="role" :class="{ 'role--on': role === 'student' }">
          <input v-model="role" type="radio" value="student" />
          <span class="role__text">学生</span>
        </label>
        <label class="role" :class="{ 'role--on': role === 'teacher' }">
          <input v-model="role" type="radio" value="teacher" />
          <span class="role__text">教师</span>
        </label>
        <label class="role" :class="{ 'role--on': role === 'none' }">
          <input v-model="role" type="radio" value="none" />
          <span class="role__text">匿名</span>
        </label>
      </fieldset>

      <!-- 名单：从后端拉的真实名单 -->
      <div class="field switcher__who">
        <label class="field__label" for="identity-who">
          {{ role === 'teacher' ? '教师工号' : role === 'student' ? '学生' : '匿名' }}
        </label>

        <select
          v-if="role === 'student'"
          id="identity-who"
          class="select"
          :value="identity.studentId ?? ''"
          :disabled="loading || students.length === 0"
          @change="onPickStudent"
        >
          <option value="" disabled>
            {{ loading ? '加载中…' : students.length === 0 ? '（名单为空）' : '选一个学生' }}
          </option>
          <option v-for="s in students" :key="s.id" :value="s.id">
            #{{ s.id }} · {{ s.student_no }} · {{ s.name }}
          </option>
        </select>

        <select
          v-else-if="role === 'teacher'"
          id="identity-who"
          class="select"
          :value="identity.teacherStaffNo ?? ''"
          :disabled="loading || teachers.length === 0"
          @change="onPickTeacher"
        >
          <option value="" disabled>
            {{ loading ? '加载中…' : teachers.length === 0 ? '（名单为空）' : '选一个教师' }}
          </option>
          <option v-for="t in teachers" :key="t.id" :value="t.staff_no">
            {{ t.staff_no }} · {{ t.name }}
          </option>
        </select>

        <p v-else class="switcher__anon">
          没有身份也能读全部列表与大屏（后端 47 个 GET 一律匿名），但任何写入都会
          <code class="data">401 unauthenticated</code>。
        </p>
      </div>

      <!-- 业务日 -->
      <div class="field switcher__asof">
        <label class="field__label" for="identity-asof">业务日 as_of</label>
        <input id="identity-asof" v-model="asOf" class="input" type="date" />
        <p class="switcher__note">
          <template v-if="asOfIsDemoDay">
            ✓ 这就是<strong>演示库的业务日</strong>（学期第 6 周的周日）。
          </template>
          <template v-else>
            ⚠️ 演示库的业务日是
            <button type="button" class="linklike num" @click="identity.resetAsOf()">
              {{ DEMO_AS_OF }}
            </button>
            。用别的日期很可能查不到数据（周报只在周日生成、处方有微周期有效期）。
          </template>
        </p>
      </div>
    </div>

    <p class="switcher__summary">
      <span class="caps">当前身份</span>
      <strong class="data">{{ identity.summary }}</strong>
      <span class="switcher__counts num">
        名单：{{ students.length }}/{{ studentTotal ?? '—' }} 学生 ·
        {{ teachers.length }}/{{ teacherTotal ?? '—' }} 教师
      </span>
    </p>

    <p v-if="studentTruncated || teacherTruncated" class="switcher__warn">
      ⚠️ 名单被 <code class="data">limit={{ ROSTER_LIMIT }}</code>（后端的上界）截断了，
      下拉框里少人。要找人请用管理台的分页。
    </p>

    <p v-if="loadFailure" class="switcher__warn">{{ loadFailure }}</p>
  </section>
</template>

<style scoped>
.switcher {
  padding: var(--space-3) var(--space-4);
  background: var(--paper-raised);
  border: var(--border-hairline);
  box-shadow: var(--shadow-paper);
}

.switcher__row {
  display: grid;
  grid-template-columns: auto minmax(0, 1.4fr) minmax(0, 1fr);
  gap: var(--space-4);
  align-items: start;
  margin-block-start: var(--space-3);
}

@media (max-width: 900px) {
  .switcher__row {
    grid-template-columns: minmax(0, 1fr);
  }
}

.switcher__roles {
  border: none;
  padding: 0;
  display: flex;
  gap: var(--space-1);
}

.switcher__roles legend {
  color: var(--ink-soft);
  padding: 0;
  margin-block-end: var(--space-1);
}

.role {
  display: inline-flex;
  align-items: center;
  cursor: pointer;
}

.role input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.role__text {
  display: inline-block;
  padding: var(--space-2) var(--space-3);
  border: 2px solid var(--ink);
  border-radius: var(--radius-sharp);
  font-family: var(--font-display);
  font-weight: var(--fw-display-700);
  font-size: var(--fs-small);
  letter-spacing: var(--tracking-caps);
  background: var(--paper);
  color: var(--ink);
}

.role--on .role__text {
  background: var(--track);
  border-color: var(--track);
  color: var(--paper);
  box-shadow: 2px 2px 0 var(--ink);
}

.role input:focus-visible + .role__text {
  outline: var(--focus-ring);
  outline-offset: var(--focus-offset);
}

.switcher__who .select {
  font-size: var(--fs-small);
}

.switcher__anon {
  font-size: var(--fs-small);
  color: var(--ink-soft);
}

.switcher__note {
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.switcher__summary {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2);
  margin-block-start: var(--space-3);
  padding-block-start: var(--space-2);
  border-block-start: var(--border-hairline);
  font-size: var(--fs-small);
}

.switcher__summary .caps {
  color: var(--ink-faint);
}

.switcher__counts {
  margin-inline-start: auto;
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.switcher__warn {
  margin-block-start: var(--space-2);
  padding: var(--space-2);
  background: var(--amber-wash);
  color: var(--amber-on-paper);
  font-size: var(--fs-small);
}

.linklike {
  background: none;
  border: none;
  padding: 0;
  color: inherit;
  font: inherit;
  text-decoration: underline;
  cursor: pointer;
}

/* 深底（教师大屏上也要能换身份：大屏是投屏的，换班靠它） */
.surface-ink .switcher {
  background: var(--ink-raised);
  border-color: var(--rule-hairline-on-ink);
  box-shadow: none;
}

.surface-ink .switcher__summary {
  border-color: var(--rule-hairline-on-ink);
  color: var(--paper-soft);
}

.surface-ink .switcher__note,
.surface-ink .switcher__anon,
.surface-ink .switcher__summary .caps {
  color: var(--paper-faint);
}

.surface-ink .role__text {
  background: transparent;
  border-color: var(--paper);
  color: var(--paper);
}

.surface-ink .role--on .role__text {
  background: var(--track-on-ink);
  border-color: var(--track-on-ink);
  color: var(--ink);
  box-shadow: 2px 2px 0 var(--offset-shadow-on-ink);
}

.surface-ink .switcher__warn {
  background: var(--amber-wash-on-ink);
  color: var(--amber-on-ink);
}
</style>
