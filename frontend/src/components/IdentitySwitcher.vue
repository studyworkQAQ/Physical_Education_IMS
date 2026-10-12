<script setup lang="ts">
/**
 * `IdentitySwitcher.vue` —— **「当前身份 + 登出」**（Plan 05A Task 3 改造）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 它此前是「代替登录页」的那个身份切换器，那一版已经退场
 * ---------------------------------------------------------------------------
 * Plan 04 的文件头逐字写着「本系统不做真实登录/鉴权。身份走两个请求头…
 * 故这里做一件事：把「我是谁」变成一个可以随手换的下拉框」。
 * Plan 05A 做了真实鉴权（计划 §4.3 逐字裁定：「`IdentitySwitcher.vue` → 换成一个
 * 『当前身份 + 登出按钮』的组件（**开发模式下额外保留切换能力**）」），故本组件今天是
 * **两半**：
 *
 * 1. **会话条（永远渲染）**：后端认出的那个人（`stores/session.ts` 的 `summary` +
 *    一个 role pill）+ **登出按钮** + 业务日 `as_of` 的输入 +
 *    守卫/过期写下的那一句 `notice`。
 *    ⚠️ **`as_of` 留在本组件里**（它此前就住在这里）：它是演示口径的一部分
 *    （缺省 `2025-10-12` = 学期第 6 周的周日），与「我是谁」无关，
 *    而它是全站唯一一个能改业务日的入口。
 * 2. **切换器（仅 `import.meta.env.DEV`）**：原来那两个下拉框。⚠️ 它只在
 *    后端 `PE_ALLOW_HEADER_IDENTITY=1` 时有效力（生产缺省 `"0"` = 只认 cookie），
 *    而 `client.ts` 也只在 DEV 构建里注入那两个头。故它是**开发工具**，
 *    生产构建里 `import.meta.env.DEV` 是编译期 `false`、那一半被整个摇掉。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 登出为什么「一定成功」（即使后端那一次失败）
 * ---------------------------------------------------------------------------
 * `POST /api/auth/logout` 在**没有会话**时回 401（后端 `current_session` 的判定），
 * 而那时用户想做的事正是「回到未登录状态」。把 401 抛回去会让登出按钮在会话已过期
 * 之后**点不动**（表现为一条红色横幅 + 仍然停在原页）。故 `session.logout()`
 * 吞掉那一次失败、只保证本地状态被清空（逐字理由见那个 action 的 docstring）。
 * ⚠️ 代价如实记：cookie 是 `HttpOnly` 的、前端清不掉它，故「服务端那一次失败」时
 * 浏览器里还留着一个 cookie —— 但服务端那一行会在 `SESSION_TTL`（2 小时）之后自己过期，
 * 而 UI 已经与现实一致（未登录）。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError } from '../api/client'
import { listStudents, listTeachers } from '../api/endpoints'
import type { StudentListItem, TeacherListItem } from '../api/types'
import { DEMO_AS_OF, useIdentityStore } from '../stores/identity'
import { useSessionStore } from '../stores/session'
import { useApiError } from './ApiErrorBanner.vue'
import SectionHead from './SectionHead.vue'

/** `limit` 的上界。⚠️ 与后端 `deps.Page` 的 `Query(ge=1, le=200)` 同源。 */
const ROSTER_LIMIT = 200

/** ⚠️ 编译期常量：生产构建里下面那一半切换器整个不存在。 */
const IS_DEV = import.meta.env.DEV

const identity = useIdentityStore()
const session = useSessionStore()
const router = useRouter()
const { raise } = useApiError()

/* ==========================================================================
   ① 会话条（永远渲染）
   ========================================================================== */

const loggingOut = ref(false)

/** role 的那一枚 pill 上写的字。⚠️ 管理员与教师要**能分开看**：
 *  管理台的 26 个写入操作只对 `admin` 开放，而两者的 `kind` 都是 `teacher`
 *  （用户 2026-10-12 裁定：管理员就是一行 `role='admin'` 的 `teacher`）。 */
const roleLabel = computed(() => {
  if (session.kind === 'student') return 'STUDENT'
  if (session.role === 'admin') return 'ADMIN'
  if (session.kind === 'teacher') return 'TEACHER'
  return 'ANONYMOUS'
})

async function onLogout(): Promise<void> {
  loggingOut.value = true
  try {
    await session.logout()
    session.setNotice('已登出（服务端那一行 user_session 已被吊销，旧 cookie 立刻失效）。')
    await router.replace('/login')
  } finally {
    loggingOut.value = false
  }
}

/* ==========================================================================
   ② 业务日 as_of（演示口径的一部分，与会话无关）
   ========================================================================== */

const asOf = computed({
  get: () => identity.asOf,
  set: (next: string) => identity.setAsOf(next),
})

/** 业务日是不是演示库的那一天。⚠️ 不是就提醒：那是「查不到数据」最常见的原因。 */
const asOfIsDemoDay = computed(() => identity.asOf === DEMO_AS_OF)

/* ==========================================================================
   ③ DEV-only 的请求头身份切换器
   ========================================================================== */

const students = ref<StudentListItem[]>([])
const teachers = ref<TeacherListItem[]>([])
const studentTotal = ref<number | null>(null)
const teacherTotal = ref<number | null>(null)
const loading = ref(false)
/** 拉名单失败时的一句本地提示。⚠️ 它**不**替代横幅：横幅说「后端怎么了」，
 *  这一句说「所以这个下拉框现在是空的」—— 用户看的是下拉框。 */
const loadFailure = ref('')

/** 当前选中的**开发期**角色。⚠️ 写成 computed 的 getter/setter，于是三个单选按钮
 *  与 store 只有一个数据源（store），不存在「按钮显示学生、store 里是教师」那一档。 */
const devRole = computed<'student' | 'teacher' | 'none'>({
  get: () => identity.role ?? 'none',
  set: (next) => {
    if (next === 'none') identity.clearIdentity()
    else if (next === 'student') pickStudent(identity.studentId ?? students.value[0]?.id ?? null)
    else pickTeacher(identity.teacherStaffNo ?? teachers.value[0]?.staff_no ?? null)
  },
})

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
  identity.becomeStudent(studentId, found ? `${found.student_no} ${found.name}` : identity.studentLabel)
}

function pickTeacher(staffNo: string | null): void {
  if (staffNo === null) return
  const found = teachers.value.find((t) => t.staff_no === staffNo)
  identity.becomeTeacher(staffNo, found ? found.name : identity.teacherLabel)
}

async function loadRosters(): Promise<void> {
  // ⚠️ **Plan 05A Task 5 之后 `GET /api/students` 与 `GET /api/teachers` 要教职身份**
  //    （那两个列表是绑定口令的验身材料，匿名可读等于谁都能给谁绑口令）。
  //    故只在「当前会话是教职」时才拉：一个学生会话在这里只会拿到 403，
  //    而那一条 403 会把横幅占满、把真因（「这一半是开发工具」）盖掉。
  if (!IS_DEV || !session.isStaff) return
  loading.value = true
  loadFailure.value = ''
  try {
    // ⚠️ 两个请求并发（`Promise.all`）：它们互不依赖，串行等于把一次 RTT 变成两次。
    const [studentPage, teacherPage] = await Promise.all([
      listStudents({ limit: ROSTER_LIMIT }),
      listTeachers({ limit: ROSTER_LIMIT }),
    ])
    students.value = studentPage.items
    teachers.value = teacherPage.items
    studentTotal.value = studentPage.total
    teacherTotal.value = teacherPage.total

    // ⚠️ 名单到了之后，把 store 里**持久化的那一个身份**回填上它的显示名。
    if (identity.role === 'student' && identity.studentId !== null) {
      pickStudent(identity.studentId)
    } else if (identity.role === 'teacher' && identity.teacherStaffNo !== null) {
      pickTeacher(identity.teacherStaffNo)
    }
  } catch (err) {
    loadFailure.value =
      err instanceof ApiError
        ? `名单没拉到（${err.code}）：这一半是开发工具，它要后端 PE_ALLOW_HEADER_IDENTITY=1，而读名单本身要一个教职会话。`
        : '名单没拉到（不是后端回的错误，看浏览器控制台）。下面两个下拉框是空的。'
    if (err instanceof ApiError) raise(err)
  } finally {
    loading.value = false
  }
}

/** 超过 `limit` 上界时提示缺人。⚠️ 不静默。 */
const studentTruncated = computed(
  () => studentTotal.value !== null && studentTotal.value > students.value.length,
)
const teacherTruncated = computed(
  () => teacherTotal.value !== null && teacherTotal.value > teachers.value.length,
)

onMounted(loadRosters)
// ⚠️ 登录/登出之后重新拉一次（`isStaff` 从 false 变 true 的那一刻才有名单可拉）。
watch(() => session.isStaff, loadRosters)
</script>

<template>
  <section class="switcher" aria-label="当前身份">
    <SectionHead :index="1" label="IDENTITY" />

    <!-- ① 会话条：后端认出的那个人 + 登出 -->
    <div class="switcher__session">
      <p class="switcher__who">
        <span class="caps">当前身份</span>
        <span class="pill" :class="{ 'pill--green': session.isAuthenticated }">{{ roleLabel }}</span>
        <strong class="data">{{ session.summary }}</strong>
      </p>

      <div class="switcher__actions">
        <button
          v-if="session.isAuthenticated"
          type="button"
          class="btn btn--ghost btn--sm"
          :disabled="loggingOut"
          @click="onLogout()"
        >
          {{ loggingOut ? '登出中…' : '登出' }}
        </button>
        <RouterLink v-else class="btn btn--primary btn--sm" :to="{ path: '/login', query: { next: $route.fullPath } }">
          去登录 →
        </RouterLink>
      </div>
    </div>

    <!-- 守卫弹回来 / 会话过期 / 登出之后写下的那一句 -->
    <p v-if="session.notice" class="switcher__warn" role="status">{{ session.notice }}</p>

    <div class="switcher__row">
      <!-- ② 业务日 -->
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

      <!-- ③ DEV-only：请求头身份切换器 -->
      <template v-if="IS_DEV">
        <fieldset class="switcher__roles">
          <legend class="caps">开发期请求头</legend>
          <label class="role" :class="{ 'role--on': devRole === 'student' }">
            <input v-model="devRole" type="radio" value="student" />
            <span class="role__text">学生</span>
          </label>
          <label class="role" :class="{ 'role--on': devRole === 'teacher' }">
            <input v-model="devRole" type="radio" value="teacher" />
            <span class="role__text">教师</span>
          </label>
          <label class="role" :class="{ 'role--on': devRole === 'none' }">
            <input v-model="devRole" type="radio" value="none" />
            <span class="role__text">不发头</span>
          </label>
        </fieldset>

        <div class="field switcher__pick">
          <label class="field__label" for="identity-who">
            {{ devRole === 'teacher' ? '教师工号' : devRole === 'student' ? '学生' : '（不发身份头）' }}
          </label>

          <select
            v-if="devRole === 'student'"
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
            v-else-if="devRole === 'teacher'"
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
            真实的身份载体是 <code class="data">pe_session</code> cookie（浏览器自己带）。
            这两个请求头只在后端 <code class="data">PE_ALLOW_HEADER_IDENTITY=1</code>
            时被接受（生产缺省 <code class="data">0</code>），故本切换器是开发工具。
          </p>
        </div>
      </template>
    </div>

    <p class="switcher__summary">
      <span v-if="IS_DEV" class="switcher__counts num">
        名单：{{ students.length }}/{{ studentTotal ?? '—' }} 学生 ·
        {{ teachers.length }}/{{ teacherTotal ?? '—' }} 教师
      </span>
      <span class="switcher__counts num">会话状态 {{ session.status }}</span>
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
  background: var(--surface-raise);
  border: var(--border-hairline);
  border-radius: var(--radius-lg);
}

.switcher__session {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-block-start: var(--space-3);
}

.switcher__who {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2);
  font-size: var(--fs-small);
}

.switcher__who .caps {
  color: var(--ink-faint);
}

.btn--sm {
  padding: var(--space-1) var(--space-2);
  font-size: var(--fs-micro);
}

.switcher__row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1.4fr);
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
  border: 1px solid var(--border-input);
  border-radius: var(--radius-btn);
  font-family: var(--font-ui);
  font-weight: var(--fw-600);
  font-size: var(--fs-small);
  background: var(--surface-raise);
  color: var(--ink);
  transition:
    background-color var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.role:hover .role__text {
  border-color: var(--primary);
  background: var(--primary-faint);
  color: var(--primary-press);
}

/* 选中的那一档：一整块主蓝 + 白字（5.73:1，过 AA） */
.role--on .role__text {
  background: var(--primary);
  border-color: var(--primary);
  color: var(--on-primary);
}

.role input:focus-visible + .role__text {
  outline: var(--focus-ring);
  outline-offset: var(--focus-offset);
}

.switcher__pick .select {
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

.switcher__counts {
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.switcher__counts + .switcher__counts {
  margin-inline-start: auto;
}

.switcher__warn {
  margin-block-start: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--amber-faint);
  color: var(--amber);
  border-radius: var(--radius);
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

/* ⚠️ Plan 05B：这里原有 7 条 `.surface-board .switcher__xxx` 的覆盖（大屏是深底时
   的第二套对比度，含「教师大屏上也要能登出」那一档）。大屏翻浅底之后
   **全站只有一套颜色**，故整组删掉 —— 它里面还引用了已删除的 `--paper`。 */
</style>
