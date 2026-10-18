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
  bindWithToken,
} from '../../api/auth'
import SectionHead from '../../components/SectionHead.vue'
import { useFormValidity } from '../../composables/useFormValidity'
import { useSessionStore } from '../../stores/session'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()

const rawKind = route.query.kind
const kind = ref<AuthKind>(rawKind === 'teacher' ? 'teacher' : 'student')

/* ---------------------------------------------------------------------------
 * ⚠️⚠️ Plan 08 Task 4：**令牌档**（`/bind?token=…`）
 * ---------------------------------------------------------------------------
 * ⚠️ **缺省档（不带 `?token=`）的 UI 一格都没变** —— 这是派单 §2 第 8 条的逐字要求，
 * 而它的可执行形式是下面这一个 `v-if`：**没有** `?token=` 时 `tokenMode` 恒为
 * `false`，于是渲染出来的是与 Plan 08 Task 4 之前**逐字相同**的那一棵 DOM
 * （同样的两个 radio、同样的 `#bind-student-no` / `#bind-birth` /
 * `#bind-staff-no` / `#bind-name`、同样的 `.auth__fine` 那一句）。
 * ⚠️ 守卫是 `scripts/smoke.mjs` 第 14 步的 `/bind` 那一拍：它**真打开** `/bind`
 * （不带查询串），断言 ① `#bind-token` **不存在** ② 那四个既有输入框**都在**
 * ③ radio 恰好 **2** 个（不是 3 个）—— 少了任何一拍，「顺手加第三个 radio」
 * 这个最容易被做的改法会绿着通过。
 *
 * ⚠️ **前端刻意不猜 `PE_ALLOW_SELF_BIND` 那个开关**（派单 §2 第 8 条逐字要求
 * 「开关是**服务端**的事，前端不该猜」）：那一格是**服务端**的环境变量，
 * 前端读不到它，而 `/openapi.json` 也**刻意不含**它（`tests/test_main.py` 的
 * `test_the_trial_switch_never_touches_the_openapi_document` 那一条同族：
 * 把部署档位回给匿名等于告诉探测者「这一台关掉了自助绑定」）。
 * ⇒ 于是关掉开关之后，一个走缺省档的用户会**提交一次、拿到后端那句 403 原文**
 * （那句原文点名了 `PE_ALLOW_SELF_BIND` 并指路 `bind-with-token`），
 * 而不是页面预先变形状。⚠️ 代价（如实记）：多一次往返。
 * 而**正确的**切换姿势是运维在关掉开关的同时把链接换成
 * `/bind?token=…` 发给新生（管理台第 06 块签发时就把那条链接给出来了）。
 *
 * ⚠️ **令牌走 URL 的代价（如实记，硬规矩 #39）**：一个走查询串的凭据会进
 * 浏览器历史，也可能经 `Referer` 出门。本原型接受它，三条理由：
 * ① 令牌是**一次性 + 7 天有效 + 限流 3 次**，而它兑换掉之后就废了；
 * ② 本页**没有**任何跨源子资源（一个 `Referer` 都发不出去）；
 * ③ 管理台那一格**同时**给出明文本身（`#bt-plaintext`），故运维可以完全不用链接、
 *   改用手抄/粘贴 —— 那一路不进历史。
 * ⚠️ 而 `audit_log` 与 `read_audit_log` 两张表**都读不到查询串**
 * （前者存 `request.url.path`、后者存路由**模板**，逐字理由各在它们的模型注释里），
 * 故令牌**不会因为走 URL 而落进审计**。
 */
const rawToken = route.query.token
const tokenMode = typeof rawToken === 'string' && rawToken.trim() !== ''
/** 令牌档下那一格输入框的初值 = URL 上带来的那串（⚠️ 用户可以改掉它，
 *  例如他把链接里的令牌抄错了半个字符时可以直接在框里改）。 */
const token = ref(tokenMode ? String(rawToken).trim() : '')

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

/** 提交前的**本地**四道（后端只有第一道的对应物）。
 *  ⚠️ **Plan 08 Task 4 起它是两档**：令牌档只判「令牌 + 口令 + 确认」三格，
 *  而**不判**出生日期/姓名 —— 那一档的验身材料**就是令牌**
 *  （`birth` 一个字都不参与判定，那正是这条更强的路存在的全部理由）。 */
function localProblem(): string {
  if (tokenMode) {
    if (token.value.trim() === '') {
      return '请把教务干事给你的绑定令牌填上（它的形状是 `<16 个字符>.<32 个字符>`）。'
    }
  } else {
    const name = (kind.value === 'student' ? studentNo.value : staffNo.value).trim()
    if (name === '') return `请把${loginLabel.value}填上。`
    if (kind.value === 'student' && !/^\d{4}-\d{2}-\d{2}$/.test(birth.value)) {
      return '请选择出生日期（后端要一个 ISO 的 YYYY-MM-DD；它会与 student.birth 那一列逐字比）。'
    }
    if (kind.value === 'teacher' && teacherName.value.trim() === '') {
      return '请把姓名填上（它是教师那一档的验身材料，要与 teacher.name 逐字相同）。'
    }
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
  try {
    // ⚠️ **令牌档**：请求体只有 `token` + `password` 两格（令牌自带目标，
    //    故这里**不交** kind / 学号 / 出生日期；逐字理由见 `api/auth.ts` 的
    //    `bindWithToken`）。⚠️ 而 204 之后**自己再登录一次**这件事与自助档
    //    逐字相同（后端刻意不回 `Set-Cookie`），故下面那一段 `session.login`
    //    要一个**登录名** —— 令牌档下它来自 204 之前的响应体吗？**不**：
    //    后端 204 **没有体**，故本页**读不出**学号。⚠️ 处置是走 `/login`
    //    并带上「绑定已经成功了」那一句提示（与既有的「自动登录失败」那一档
    //    **同一个去处**，故本块没有引入第二种失败形状）。
    if (tokenMode) {
      await bindWithToken(token.value.trim(), password.value)
      session.setNotice(
        '口令已经绑定成功了。⚠️ 令牌档下本页读不出你的学号/工号（后端 204 没有响应体），'
        + '请在下一页填一次登录名 + 刚设的口令。',
      )
      await router.replace({ path: '/login', query: { kind: kind.value } })
      return
    }
    const name = (kind.value === 'student' ? studentNo.value : staffNo.value).trim()
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
      <!-- ⚠️ 下面这一段与再下面那三个 `<template>` 一律带 `!tokenMode`：
           **缺省档（不带 `?token=`）渲染出来的 DOM 与 Plan 08 Task 4 之前逐字相同**，
           守卫是 `smoke.mjs` 第 14 步的 `/bind` 那一拍（逐字理由见 script 顶部那段）。 -->
      <p v-if="!tokenMode" class="auth__lede">
        名册由教务干事建好，口令由本人第一次自己设。⚠️ 本页<strong>不建账号</strong>：
        一个不在册的{{ loginLabel }}会得到 <code class="data">403 forbidden</code>。
      </p>
      <p v-else class="auth__lede">
        教务干事给了你一张<strong>一次性绑定令牌</strong>：填上它 + 一个新口令即可。
        ⚠️ 这一档<strong>不要</strong>出生日期或姓名 —— 令牌<strong>自带</strong>你的学号/工号，
        故请求体只有 <code class="data">token</code> 与 <code class="data">password</code> 两格。
        ⚠️ 一张令牌<strong>只能兑换一次</strong>、且<strong>7 天</strong>内有效。
      </p>

      <p v-if="session.notice" class="auth__notice" role="status">{{ session.notice }}</p>

      <form :ref="bindForm" class="auth__form" @submit.prevent="submit()">
        <fieldset v-if="!tokenMode" class="auth__kinds">
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

        <!-- 令牌档：一格输入框（⚠️ `id="bind-token"`，smoke 那一拍钉它在缺省档下**不存在**） -->
        <template v-if="tokenMode">
          <div class="field">
            <label class="field__label" for="bind-token">绑定令牌（验身材料）</label>
            <input
              id="bind-token"
              v-model="token"
              class="input data"
              type="text"
              autocomplete="one-time-code"
              spellcheck="false"
              :disabled="busy"
              required
            />
            <p class="auth__hint">
              请求体里那一格叫 <code class="data">token</code>，形状是
              <code class="data">&lt;16 个字符&gt;.&lt;32 个字符&gt;</code>。
              ⚠️ 后端<strong>只存它的哈希</strong>（与口令同一条口径：
              <code class="data">app/auth/passwords.py</code> 的 PBKDF2），
              故教务干事也<strong>读不回</strong>它 —— 弄丢了只能<strong>重签一张</strong>。
              ⚠️ 用过了是 <code class="data">409 bind_token_spent</code>、
              过期是 <code class="data">403 bind_token_expired</code>
              （两档<strong>刻意可区分</strong>：走到那里的人已经持有那张凭据，
              故告诉他「它废了」不泄漏任何东西，而不告诉他会让一个合法新生
              反复重输、然后被限流锁 60 分钟）。
            </p>
          </div>
        </template>

        <!-- 学生：学号 + 出生日期 -->
        <template v-else-if="kind === 'student'">
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
        <template v-else-if="!tokenMode">
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
            {{ busy ? '绑定中…' : (tokenMode ? '用令牌绑定口令' : '绑定口令并登录') }}
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

    <p v-if="!tokenMode" class="auth__fine">
      ⚠️ 验身材料（出生日期 / 姓名）在本原型里是**弱材料**：读那两份名册
      <strong>要教职身份</strong>（它们正是绑定口令的验身材料，故收得最紧）。
      逐字局限见 spec §1.2 与 §13。
    </p>
    <!-- ⚠️ 令牌档的那一句：它**刻意**把「这一条路更强、而缺省那一条今天仍然开着」
         两件事一次说清（spec §13.26 / §13.15 第 4 条）。⚠️ 而缺省档下这一段
         **一个字节都不渲染**（`v-if`），故上面那一句在缺省档下逐字未变。 -->
    <p v-else class="auth__fine">
      ⚠️ 你走的是<strong>一次性绑定令牌</strong>那一条路：它是本系统<strong>更强</strong>的
      验身材料（192 bit 的随机秘密，<code class="data">birth</code> 一个字都不参与判定）。
      ⚠️ 而「学号 + 出生日期」那一条<strong>自助</strong>路径今天<strong>默认仍然开着</strong>
      （服务端环境变量 <code class="data">PE_ALLOW_SELF_BIND</code>，缺省
      <code class="data">1</code>）—— 要把它关掉是<strong>运维</strong>的动作，
      前端读不到那一格、也<strong>刻意不猜</strong>它。逐字局限见 spec §1.2 第 4 条与 §13.26。
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
