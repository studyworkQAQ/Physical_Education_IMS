<script setup lang="ts">
/**
 * `views/auth/Login.vue` —— **登录页**（Plan 05A Task 3 / 计划 §4.1）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 只有**两档**身份，管理员不单列
 * ---------------------------------------------------------------------------
 * 用户 2026-10-12 逐字裁定「管理员这个角色接管管理台」，而它的落地形式是
 * **一行 `role='admin'` 的 `teacher`**（不是第三张表、也不是第三种 `kind`）。
 * 后端 `LoginCreate.kind` 的取值域因此只有 `student` / `teacher`
 * （唯一所有者是 `UserSession.KINDS`），故登录表单也**只有两档**。
 * ⚠️ 而**登录后跳哪个首页**由响应体里的 `role` 决定（计划 §4.1 逐字要求）：
 * 学生 → `/s/home`、教师 → `/t/dashboard`、管理员 → `/admin`。
 * 那一格的住址是 `stores/session.ts` 的 `homePath` getter（不写第二份）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 错误档一律按 `code` 分支，不按 `message`
 * ---------------------------------------------------------------------------
 * `POST /api/auth/login` 的三档（后端 `app/api/routers/auth.py` 的 `login`）：
 *  * **403 `password_not_bound`** —— 不在册**或**在册但没绑口令 → 送他去 `/bind`，
 *    并把 `kind` 与刚输的登录名带过去（省一次重输）；
 *  * **401 `invalid_credentials`** —— 绑过、口令错 → 停在本页、**清空口令框**
 *    （不清的话「再试一次」会带着一个已知错的串，而浏览器的自动填充会把它填回来）；
 *  * **422 `request_validation_failed`** —— 请求体缺字段（前端的 bug）。
 * ⚠️ 这三档**刻意可区分**（后端 `login` 的 docstring 逐字交代了：两档的下一步动作
 * 相反），代价是泄漏了「这个学号在不在册」——已登记为 spec 的已知局限。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ `?next=` 的校验（一个开放重定向的洞）
 * ---------------------------------------------------------------------------
 * 登录成功之后要回到「被守卫弹回来之前那一页」，故 `next` 从查询串里读。
 * 而**不加校验的 `next` 就是一个开放重定向**：`/login?next=https://evil.example`
 * 或 `/login?next=//evil.example`（协议相对 URL，浏览器会当成跨站）都会把用户
 * 送出去。故 {@link safeNext} 只接受「以单个 `/` 开头、且第二个字符不是 `/` 或 `\`」
 * 的串 —— 那恰好是 vue-router 认的**站内绝对路径**，其余一律退回 `homePath`。
 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiError } from '../../api/client'
import { AUTH_KINDS, type AuthKind, authAdvice } from '../../api/auth'
import SectionHead from '../../components/SectionHead.vue'
import { useSessionStore } from '../../stores/session'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()

/** 身份档位。⚠️ 初值从 `?kind=` 读（绑定页送回来的那一格），只认两个字面值。 */
const rawKind = route.query.kind
const kind = ref<AuthKind>(rawKind === 'teacher' ? 'teacher' : 'student')

/** 登录名：学生是**学号**、教师是**工号**。⚠️ 后端一个 `login` 字段承载两种，
 *  而标签必须换（一个字段名给不出两个中文标签 —— 后端 `SessionIdentityRead`
 *  的 docstring 逐字写了这个理由）。 */
const loginName = ref(typeof route.query.login === 'string' ? route.query.login : '')
const password = ref('')
const busy = ref(false)
/** 就地的一句错话（画在表单下方）。⚠️ 它**不**替代 `ApiErrorBanner`：
 *  横幅说「后端回了什么」，这一句说「你现在该做什么」。 */
const advice = ref('')
/** 403 `password_not_bound` 那一档：给出「去绑定」的入口，而不是只说一句错话。 */
const shouldBind = ref(false)

const loginLabel = computed(() => (kind.value === 'student' ? '学号' : '工号'))
const loginHint = computed(() =>
  kind.value === 'student'
    ? '演示库的学号形如 2025010004。演示口令由 backend/scripts/demo.ps1 打印（也写在 spec §13）。'
    : '演示库的工号形如 T0001；管理员也是一行 teacher（role=admin），登录时用同一档。',
)

/** 换档位时清掉上一档的输入与错话。⚠️ 学号与工号是两种格式，
 *  留着会让人以为「刚才那一串还能用」。 */
function pickKind(next: AuthKind): void {
  if (kind.value === next) return
  kind.value = next
  loginName.value = ''
  password.value = ''
  advice.value = ''
  shouldBind.value = false
}

/** `?next=` 的站内路径校验。见文件头末节。 */
function safeNext(): string {
  const raw = route.query.next
  if (typeof raw !== 'string' || raw.length === 0) return session.homePath
  if (!raw.startsWith('/')) return session.homePath
  const second = raw[1]
  if (second === '/' || second === '\\') return session.homePath
  return raw
}

async function submit(): Promise<void> {
  advice.value = ''
  shouldBind.value = false
  const name = loginName.value.trim()
  if (name === '' || password.value === '') {
    advice.value = `请把${loginLabel.value}与口令都填上。`
    return
  }
  busy.value = true
  try {
    await session.login(kind.value, name, password.value)
    session.clearNotice()
    // ⚠️ **`replace` 而不是 `push`**：登录页不该留在历史里 —— 否则「后退」
    //    会回到一个已登录用户的登录页（守卫会再把他弹回首页，表现为「后退点不动」）。
    await router.replace(safeNext())
  } catch (err) {
    advice.value = authAdvice(err, kind.value)
    shouldBind.value = err instanceof ApiError && err.code === 'password_not_bound'
    // ⚠️ 口令错就清空口令框（理由见文件头那一档）。
    if (err instanceof ApiError && err.code === 'invalid_credentials') password.value = ''
    if (err instanceof ApiError) throw err // 交给 app.config.errorHandler 进横幅
  } finally {
    busy.value = false
  }
}

/** 去绑定页，把已知的两格带过去（省一次重输）。 */
const bindQuery = computed(() => ({ kind: kind.value, login: loginName.value.trim() }))
</script>

<template>
  <section class="auth">
    <SectionHead :index="1" label="SIGN IN" />

    <div class="card auth__card">
      <p class="caps auth__kicker">PHYSICAL EDUCATION · CLOSED LOOP</p>
      <h2 class="zh-title auth__title">登录</h2>
      <p class="auth__lede">
        名册已存在、口令首次自绑。会话是一个
        <code class="data">HttpOnly</code> 的
        <code class="data">pe_session</code> cookie（故 JS 读不到它，
        「我登录了没」由 <code class="data">GET /api/auth/me</code> 回答）。
      </p>

      <!-- ⚠️ 被守卫弹回来 / 会话过期时的那一句。它**必须**在这里显示：
           用户看到的是一个登录页，而「你为什么在这里」不说的话，
           他会以为自己从来没登录过。 -->
      <p v-if="session.notice" class="auth__notice" role="status">{{ session.notice }}</p>

      <form class="auth__form" @submit.prevent="submit()">
        <fieldset class="auth__kinds">
          <legend class="field__label">我是</legend>
          <label
            v-for="option in AUTH_KINDS"
            :key="option"
            class="kind"
            :class="{ 'kind--on': kind === option }"
          >
            <!-- ⚠️ **`:checked` + `@change`，不是 `v-model`**：`v-model` 会先把
                 `kind` 改掉、再触发 `change`，于是 `pickKind` 里的
                 「同一个档位就直接返回」那一支恒成立，「换档位要清掉上一档的输入」
                 静默失效（学号留在框里、而标签已经变成了「工号」）。 -->
            <input
              :value="option"
              :checked="kind === option"
              type="radio"
              name="kind"
              @change="pickKind(option)"
            />
            <span class="kind__text">{{ option === 'student' ? '学生' : '教师 / 管理员' }}</span>
          </label>
        </fieldset>

        <div class="field">
          <label class="field__label" for="login-name">{{ loginLabel }}</label>
          <input
            id="login-name"
            v-model="loginName"
            class="input data"
            type="text"
            autocomplete="username"
            :disabled="busy"
            required
          />
          <p class="auth__hint">{{ loginHint }}</p>
        </div>

        <div class="field">
          <label class="field__label" for="login-password">口令</label>
          <input
            id="login-password"
            v-model="password"
            class="input"
            type="password"
            autocomplete="current-password"
            :disabled="busy"
            required
          />
        </div>

        <p v-if="advice" class="auth__advice" role="alert">{{ advice }}</p>

        <div class="auth__actions">
          <button class="btn btn--primary" type="submit" :disabled="busy">
            {{ busy ? '登录中…' : '登录' }}
          </button>
          <RouterLink class="btn btn--ghost" :to="{ path: '/bind', query: bindQuery }">
            首次使用？去绑定口令 →
          </RouterLink>
        </div>

        <p v-if="shouldBind" class="auth__hint">
          ⚠️ 后端说的是「这个{{ loginLabel }}还没有绑定口令（或不在名册上）」。
          绑定要<strong>验身材料</strong>：学生是学号 + 出生日期，教师是工号 + 姓名。
        </p>
      </form>
    </div>

    <p class="auth__fine">
      本原型<strong>不做</strong>口令找回 / 登录失败锁定 / 图形验证码 / OAuth。
      忘了口令要找教务干事把 <code class="data">password_hash</code> 置回
      <code class="data">NULL</code>（逐字局限见 spec §1.2 与 §13）。
    </p>
  </section>
</template>

<style scoped>
/* ⚠️ 一律取自 tokens.css（`npm run check:tokens` 会扫本文件里的色值字面量）。
   ⚠️ 也**刻意不引入第二套设计语言**：Plan 05B 会把全站换肤成「北欧公共标识」，
   而那时本页跟着 `tokens.css` 一起变 —— 自创一套的话 05B 要重做两遍（计划 §1 非目标第 5 条）。 */
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
