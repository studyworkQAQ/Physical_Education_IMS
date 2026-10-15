<script setup lang="ts">
/**
 * `views/auth/Bind.vue` —— **首次绑定口令**（Plan 05A Task 3 / 计划 §4.1）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 这是「名册已存在 + 首次绑定密码」，**不是自助注册**
 * ---------------------------------------------------------------------------
 * 用户 2026-10-12 逐字裁定。故本页**不建学生行/教师行**（那是管理员经
 * `POST /api/students` / `POST /api/teachers` 做的事，Plan 05A Task 2 之后**仅管理员**），
 * 它只给一个**已在册**的账号设第一份口令。一个不在册的学号在后端是
 * **403 `forbidden`**、不是 201。
 *
 * 验身材料（后端 `app/api/schemas/auth.py`，字段名与 DB 列名逐字相同）：
 *
 * | 档位 | 请求体 | 验身材料 |
 * |---|---|---|
 * | 学生 | `{student_no, birth, password}` | 学号 + **出生日期** |
 * | 教师 | `{staff_no, name, password}` | 工号 + 姓名 |
 *
 * ⚠️ **是 `birth` 不是 `birth_date`**（计划 §3.2 那一格被 Task 1 的实现者顶回并改正：
 * `student` 表那一列实测就叫 `birth`，而本仓约定「请求体字段名与 DB 列名逐字相同」）。
 *
 * ⚠️⚠️ **验身材料本身是弱材料**（如实说明，不藏）：Plan 05A Task 5 之前
 * `GET /api/students` 匿名返回全部 60 人的 `birth`、`GET /api/teachers` 匿名返回
 * 全部工号与姓名 —— 于是「读过那两个列表的人」可以给任何账号绑口令。
 * Task 5 把那 4 个读操作改成了**要教职身份**（匿名 401），故这一页的验身材料
 * 今天挡的是「校外的人」，而**不挡**「一个已登录的教师/管理员」。
 * 逐字局限见 spec §1.2 与 §13。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 前端拦两道、后端是唯一权威
 * ---------------------------------------------------------------------------
 * 1. **弱口令（< 8 字符）前端就拦**（省一次往返）。⚠️ 后端的
 *    **422 `unprocessable_value`** 仍然是唯一权威（`app/auth/passwords.py` 的
 *    `ensure_acceptable`），故 `MIN_PASSWORD_LENGTH` 在这里只是它的一个**镜像**，
 *    两处不一致时以后端为准（那一档会表现为一句后端原文的 message）。
 * 2. **两次输入不一致要在前端拦**（派单逐字要求）：⚠️ **后端不管这一格** ——
 *    它的请求体里只有一个 `password` 字段，「确认口令」纯粹是一个 UI 概念。
 *    不拦的话「打错了确认框」会静默地把第一格设成口令。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 成功之后**自己再登录一次**
 * ---------------------------------------------------------------------------
 * 后端 `bind_student` / `bind_teacher` 成功是 **204 且不回 `Set-Cookie`**
 * （刻意：「绑定成功即已认证」会让「验身材料泄漏」直接等于「账号被接管」）。
 * 故本页在 204 之后自己打一次 `POST /api/auth/login`，然后按 `role` 跳首页。
 * ⚠️ 那一次登录若失败（例如口令在这一瞬间被别人改了），本页**不静默**：
 * 它把用户送去 `/login` 并带上刚输的登录名，同时说清「绑定已经成功了」。
 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiError } from '../../api/client'
import {
  AUTH_KINDS,
  type AuthKind,
  MIN_PASSWORD_LENGTH,
  authAdvice,
  bindStudent,
  bindTeacher,
} from '../../api/auth'
import SectionHead from '../../components/SectionHead.vue'
import { useFormValidity } from '../../composables/useFormValidity'
import { useSessionStore } from '../../stores/session'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()

const rawKind = route.query.kind
const kind = ref<AuthKind>(rawKind === 'teacher' ? 'teacher' : 'student')

/** 学生：学号 + 出生日期；教师：工号 + 姓名。⚠️ 四个 ref 都常驻（不按档位删），
 *  于是「切档位再切回来」不会丢掉已经填好的那一半。 */
const studentNo = ref(typeof route.query.login === 'string' && rawKind !== 'teacher' ? route.query.login : '')
const birth = ref('')
const staffNo = ref(typeof route.query.login === 'string' && rawKind === 'teacher' ? route.query.login : '')
const teacherName = ref('')

const password = ref('')
const confirm = ref('')
const busy = ref(false)
const advice = ref('')
/** 409 `password_already_bound` 那一档：给出「去登录」的入口。 */
const alreadyBound = ref(false)

/** ⚠️ **Plan 07 Task 5b 缺陷 ①（同族那一格）**：本页六个输入框都带 `required`
 *  （含 `type="date"` 的出生日期），于是「留一格空就点绑定」会被**浏览器原生校验**
 *  拦在 `submit` 之前 —— 下面 `localProblem()` 那四道本地检查**一道都不会跑**
 *  （它住在 `submit()` 里，而 `submit` 事件不触发）。接上
 *  `composables/useFormValidity.ts` 之后，那一档在页面上留得下来。 */
const { notice: formNotice, bind: bindForm, clear: clearFormNotice } = useFormValidity()

/** 登录名的中文标签（两档各一个）。 */
const loginLabel = computed(() => (kind.value === 'student' ? '学号' : '工号'))
/** 请求体里那一格的名字 —— ⚠️ 显示给用户看，于是「后端说什么字段」与
 *  「本页填什么」是同一件事（`forbidden` 那一档的 message 里点的是学号/工号）。 */
const loginField = computed(() => (kind.value === 'student' ? 'student_no' : 'staff_no'))

function pickKind(next: AuthKind): void {
  if (kind.value === next) return
  kind.value = next
  advice.value = ''
  alreadyBound.value = false
  // ⚠️ 换档位时那一半字段整个不渲染（`v-if` / `v-else`），故上一次那句
  //    「没通过校验」指的可能是**已经不在 DOM 里**的那一格 —— 不清就是一句假话。
  clearFormNotice()
}

/** 提交前的**本地**四道（后端只有第一道的对应物）。 */
function localProblem(): string {
  const name = (kind.value === 'student' ? studentNo.value : staffNo.value).trim()
  if (name === '') return `请把${loginLabel.value}填上。`
  if (kind.value === 'student' && !/^\d{4}-\d{2}-\d{2}$/.test(birth.value)) {
    return '请选择出生日期（后端要一个 ISO 的 YYYY-MM-DD；它会与 student.birth 那一列逐字比）。'
  }
  if (kind.value === 'teacher' && teacherName.value.trim() === '') {
    return '请把姓名填上（它是教师那一档的验身材料，要与 teacher.name 逐字相同）。'
  }
  // ⚠️ 弱口令：前端拦一道，后端 422 是唯一权威（文件头第二节）。
  if (password.value.length < MIN_PASSWORD_LENGTH) {
    return `口令至少 ${MIN_PASSWORD_LENGTH} 个字符（现在 ${password.value.length} 个）。本原型不做复杂度规则，也不做找回，故请自己记牢。`
  }
  // ⚠️ 两次不一致：**后端不管这一格**（它的请求体里只有一个 password）。
  if (password.value !== confirm.value) return '两次输入的口令不一致。'
  return ''
}

async function submit(): Promise<void> {
  advice.value = ''
  alreadyBound.value = false
  const problem = localProblem()
  if (problem !== '') {
    advice.value = problem
    return
  }
  busy.value = true
  const name = (kind.value === 'student' ? studentNo.value : staffNo.value).trim()
  try {
    if (kind.value === 'student') {
      await bindStudent(name, birth.value, password.value)
    } else {
      await bindTeacher(name, teacherName.value.trim(), password.value)
    }
    // ⚠️ 204 之后自己登录一次（文件头末节）。
    try {
      await session.login(kind.value, name, password.value)
      session.clearNotice()
      await router.replace(session.homePath)
    } catch {
      session.setNotice(
        `口令已经绑定成功了，而随后那一次自动登录没有成功。请用刚设的口令登录一次（${loginLabel.value} ${name}）。`,
      )
      await router.replace({ path: '/login', query: { kind: kind.value, login: name } })
    }
  } catch (err) {
    advice.value = authAdvice(err, kind.value)
    alreadyBound.value = err instanceof ApiError && err.code === 'password_already_bound'
    if (err instanceof ApiError) throw err // 交给 app.config.errorHandler 进横幅
  } finally {
    busy.value = false
  }
}

const loginQuery = computed(() => ({ kind: kind.value, login: (kind.value === 'student' ? studentNo.value : staffNo.value).trim() }))
</script>

<template>
  <section class="auth">
    <SectionHead :index="1" label="FIRST USE" />

    <div class="card auth__card">
      <p class="caps auth__kicker">ROSTER EXISTS · BIND A PASSWORD</p>
      <h2 class="zh-title auth__title">首次绑定口令</h2>
      <p class="auth__lede">
        名册由教务干事建好，口令由本人第一次自己设。⚠️ 本页<strong>不建账号</strong>：
        一个不在册的{{ loginLabel }}会得到 <code class="data">403 forbidden</code>。
      </p>

      <p v-if="session.notice" class="auth__notice" role="status">{{ session.notice }}</p>

      <form :ref="bindForm" class="auth__form" @submit.prevent="submit()">
        <fieldset class="auth__kinds">
          <legend class="field__label">我是</legend>
          <label
            v-for="option in AUTH_KINDS"
            :key="option"
            class="kind"
            :class="{ 'kind--on': kind === option }"
          >
            <input
              :value="option"
              :checked="kind === option"
              type="radio"
              name="bind-kind"
              @change="pickKind(option)"
            />
            <span class="kind__text">{{ option === 'student' ? '学生' : '教师' }}</span>
          </label>
        </fieldset>

        <!-- 学生：学号 + 出生日期 -->
        <template v-if="kind === 'student'">
          <div class="field">
            <label class="field__label" for="bind-student-no">学号</label>
            <input
              id="bind-student-no"
              v-model="studentNo"
              class="input data"
              type="text"
              autocomplete="username"
              :disabled="busy"
              required
            />
            <p class="auth__hint">请求体里那一格叫 <code class="data">student_no</code>。</p>
          </div>
          <div class="field">
            <label class="field__label" for="bind-birth">出生日期（验身材料）</label>
            <input
              id="bind-birth"
              v-model="birth"
              class="input data"
              type="date"
              :disabled="busy"
              required
            />
            <p class="auth__hint">
              请求体里那一格叫 <code class="data">birth</code>（⚠️ 不是
              <code class="data">birth_date</code>：DB 列名逐字就是 <code class="data">birth</code>）。
              它与名册上那一份不符时，后端回的是与「不在册」<strong>同一档</strong>
              <code class="data">403 forbidden</code> + 同一句 message —— 刻意不给区分信号。
            </p>
          </div>
        </template>

        <!-- 教师：工号 + 姓名 -->
        <template v-else>
          <div class="field">
            <label class="field__label" for="bind-staff-no">工号</label>
            <input
              id="bind-staff-no"
              v-model="staffNo"
              class="input data"
              type="text"
              autocomplete="username"
              :disabled="busy"
              required
            />
            <p class="auth__hint">请求体里那一格叫 <code class="data">staff_no</code>。</p>
          </div>
          <div class="field">
            <label class="field__label" for="bind-name">姓名（验身材料）</label>
            <input
              id="bind-name"
              v-model="teacherName"
              class="input"
              type="text"
              autocomplete="name"
              :disabled="busy"
              required
            />
            <p class="auth__hint">
              请求体里那一格叫 <code class="data">name</code>，要与
              <code class="data">teacher.name</code> 逐字相同。
              ⚠️ 绑定<strong>不会</strong>把人变成管理员：<code class="data">role</code>
              只能由 <code class="data">POST/PATCH /api/teachers</code>（仅管理员）改。
            </p>
          </div>
        </template>

        <div class="field">
          <label class="field__label" for="bind-password">新口令</label>
          <input
            id="bind-password"
            v-model="password"
            class="input"
            type="password"
            autocomplete="new-password"
            :disabled="busy"
            required
          />
          <p class="auth__hint">
            至少 {{ MIN_PASSWORD_LENGTH }} 个字符（后端
            <code class="data">app/auth/passwords.py</code> 的
            <code class="data">MIN_PASSWORD_LENGTH</code>；不够是
            <code class="data">422 unprocessable_value</code>，且**排在 403 之前**）。
            不做复杂度规则、不做找回。
          </p>
        </div>

        <div class="field">
          <label class="field__label" for="bind-confirm">再输一次</label>
          <input
            id="bind-confirm"
            v-model="confirm"
            class="input"
            type="password"
            autocomplete="new-password"
            :disabled="busy"
            required
          />
          <p class="auth__hint">
            ⚠️ 这一格<strong>只在前端存在</strong>：后端的请求体里只有一个
            <code class="data">password</code>，「两次不一致」它管不了。
          </p>
        </div>

        <p v-if="advice" class="auth__advice" role="alert">{{ advice }}</p>

        <!-- ⚠️ 原生校验拦下提交时的那一句（Plan 07 Task 5b 缺陷 ①）。措辞的住址是
             `composables/useFormValidity.ts`，本处只用**本页既有的** `.auth__advice`
             把它画出来 ⇒ 一行新 CSS 都没加。 -->
        <p v-if="formNotice" class="auth__advice" role="alert">
          <strong>{{ formNotice.title }}</strong>
          {{ formNotice.body }}
        </p>

        <div class="auth__actions">
          <button class="btn btn--primary" type="submit" :disabled="busy">
            {{ busy ? '绑定中…' : '绑定口令并登录' }}
          </button>
          <RouterLink class="btn btn--ghost" :to="{ path: '/login', query: loginQuery }">
            ← 已经绑定过了，去登录
          </RouterLink>
        </div>

        <p v-if="alreadyBound" class="auth__hint">
          ⚠️ 后端说的是「这个{{ loginLabel }}（<code class="data">{{ loginField }}</code>）
          已经绑定过口令了」：一个账号只能绑定一次，本原型不做找回。请直接登录；
          真的忘了口令，要找教务干事把 <code class="data">password_hash</code> 置回
          <code class="data">NULL</code>。
        </p>
      </form>
    </div>

    <p class="auth__fine">
      ⚠️ 验身材料（出生日期 / 姓名）在本原型里是**弱材料**：Plan 05A Task 5 之前它们
      匿名可读，之后要教职身份才可读。逐字局限见 spec §1.2 与 §13。
    </p>
  </section>
</template>

<style scoped>
/* ⚠️ 与 `Login.vue` 共用同一套类名（`.auth*` / `.kind*`）。两份 scoped 样式里
   逐字重复的那一段是**刻意的**：Vue 的 scoped CSS 不给「跨组件共享一段规则」
   提供任何机制（`:deep()` 是往子组件里钻，不是往外共享），而把它们提到
   `styles/*.css` 里就会造出第四个布局层文件（`student/teacher/admin` 之外），
   那是 Plan 05B 换肤时要多改一处的地方。两页各一份、加起来 ~60 行，是这里最便宜的取舍。
   ⚠️ 色值与尺寸一律取自 tokens.css（`npm run check:tokens` 扫本文件）。 */
.auth {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.auth__card {
  padding: var(--space-4);
}

.auth__kicker {
  color: var(--ink-faint);
}

.auth__title {
  font-size: var(--fs-title);
  margin-block-start: var(--space-1);
}

.auth__lede {
  margin-block-start: var(--space-2);
  font-size: var(--fs-small);
  color: var(--ink-soft);
}

.auth__notice {
  margin-block-start: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-inline-start: var(--bar-accent) solid var(--amber);
  border-radius: var(--radius);
  background: var(--amber-faint);
  color: var(--amber);
  font-size: var(--fs-small);
}

.auth__form {
  margin-block-start: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.auth__kinds {
  border: none;
  padding: 0;
  display: flex;
  gap: var(--space-1);
}

.auth__kinds legend {
  color: var(--ink-soft);
  padding: 0;
  margin-block-end: var(--space-1);
}

.kind {
  display: inline-flex;
  align-items: center;
  cursor: pointer;
}

.kind input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.kind__text {
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

.kind:hover .kind__text {
  border-color: var(--primary);
  background: var(--primary-faint);
  color: var(--primary-press);
}

.kind--on .kind__text {
  background: var(--primary);
  border-color: var(--primary);
  color: var(--on-primary);
}

.kind input:focus-visible + .kind__text {
  outline: var(--focus-ring);
  outline-offset: var(--focus-offset);
}

.auth__hint {
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.auth__advice {
  padding: var(--space-2) var(--space-3);
  border-inline-start: var(--bar-accent) solid var(--red);
  border-radius: var(--radius);
  background: var(--surface-sunken);
  color: var(--red);
  font-size: var(--fs-small);
}

.auth__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
}

.auth__fine {
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}
</style>
