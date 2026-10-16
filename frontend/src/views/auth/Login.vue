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
import BrandLockup from '../../components/BrandLockup.vue'
import SectionHead from '../../components/SectionHead.vue'
import { useFormValidity } from '../../composables/useFormValidity'
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

/** ⚠️ **Plan 07 Task 5b 缺陷 ①（同族那一格）**：本页两个输入框都带 `required`，
 *  于是「留空点登录」会被**浏览器原生校验**拦在 `submit` 之前 —— 下面 `submit()`
 *  里那句「请把学号与口令都填上。」的本地检查**根本不会执行**
 *  （它住在 `submit()` 里，而 `submit` 事件不触发），用户只看到一个一闪就没的原生气泡。
 *  接上 `composables/useFormValidity.ts` 之后，那一档在页面上留得下来。 */
const { notice: formNotice, bind: bindForm, clear: clearFormNotice } = useFormValidity()

const loginLabel = computed(() => (kind.value === 'student' ? '学号' : '工号'))
/** 输入框下面那一句提示。
 *
 *  ⚠️⚠️ **学生那一档刻意只描述格式、不举具体学号**（终审 I1）：本处此前印的是
 *  「学号形如 `2025010004`」，而演示库的名册由 `app/seed/population.py` 按
 *  「入学年 + 院系码 + 序号」现造，那串**从来不在册** → 一个人照着本页自己的提示
 *  输进去，第一屏就是 403 `password_not_bound`，而那一句 403 说的是「不在名册上」，
 *  会把他支去查后端。真例子只有一个住址：`scripts/demo_bootstrap.py` 的 `[6/7]`
 *  那一步（它从库里取一个），`demo.ps1` 与 spec §13 都只指过去、不抄第二份。
 *  ⚠️ 守卫是 `scripts/smoke.mjs` 第 14 步那一拍：登录页 DOM 里出现的**每一个**
 *  登录名形状的串都必须真在册（学生档 `\d{10}`、教师档 `T\d{4}`）。
 *
 *  ⚠️ 教师那一档的 `T0001` **留着**：它是 `demo_bootstrap.py` 造出来的固定工号
 *  （`smoke.mjs` 的 `TEACHER` 常量就是它），故它是真的 —— 而上面那条守卫会钉住它。 */
const loginHint = computed(() =>
  kind.value === 'student'
    ? '学号是 10 位数字：入学年 4 位 + 院系码 2 位 + 序号 4 位。'
      + '在册的学号由 backend/scripts/demo.ps1 灌库那一步打印一个真例子；演示口令也在那里（spec §13 亦记）。'
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
  // ⚠️ 换档位是**程序**清空的（Vue 直接写 `input.value`，不触发 `input` 事件），
  //    故上一次那句「没通过校验」不会自己消失 —— 不清就是一句过期话。
  clearFormNotice()
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
    <!-- ⚠️ 品牌锁排（校徽 + 嘉庚体校名 + 系统名 + 拉丁副题 + 校训）。
         住址是 `components/BrandLockup.vue`；它排在 `SectionHead` **之上** ——
         登录页是甲方看到的第一屏，品牌先说、再说「这是第 01 块：登录」。 -->
    <BrandLockup variant="lockup" />

    <SectionHead :index="1" label="SIGN IN" />

    <div class="card auth__card">
      <!-- ⚠️ 改前这里有一行 `<p class="caps auth__kicker">` 印拉丁副题。品牌与密度波
           把锁排（含同一行副题）放到了本页顶部之后，它就变成了**同一句话印两遍**
           （实测截图上上下相隔 400px 的两个 PHYSICAL EDUCATION · LAYERED PRESCRIPTION），
           故删掉这一行与它那条 CSS —— 副题的唯一住址在锁排里。 -->
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

      <form :ref="bindForm" class="auth__form" @submit.prevent="submit()">
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

        <!-- ⚠️ 原生校验拦下提交时的那一句（Plan 07 Task 5b 缺陷 ①）。措辞的住址是
             `composables/useFormValidity.ts`，本处只用**本页既有的** `.auth__advice`
             把它画出来 ⇒ 一行新 CSS 都没加。 -->
        <p v-if="formNotice" class="auth__advice" role="alert">
          <strong>{{ formNotice.title }}</strong>
          {{ formNotice.body }}
        </p>

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

    <!-- ⚠️ 改前这一段逐字写着「本系统**不做**口令找回 / 登录失败锁定 / 图形验证码 /
         OAuth」，而**登录失败锁定自 Plan 06 Task 3 起真的在**：同一个标识在 15 分钟内
         失败 5 次 → 锁 15 分钟，而锁定档回的是与「口令错」**逐字相同**的 401
         （2026-10-16 实测：5 发坏口令 0.083/0.048/0.050/0.050/0.061 s，第 6 发
         **0.017 s** = 一次 PBKDF2 都不跑的签名；而**用正确口令也是同一份** 401 /
         82 B / sha256[:16] D6CA996C91CFADAA）⇒ 那一格是一句关于**安全**的假话，
         而它与同批交付的说明书 §6⑤ 正好相反。逐字口径见 spec §13.4.6 与 §13.20。
         ⚠️ 而这里**刻意不写具体数字**：三个阈值都是环境变量
         （PE_LOGIN_MAX_FAILS / PE_LOGIN_WINDOW_MIN / PE_LOGIN_LOCK_MIN，
         唯一所有者是 backend/app/auth/policy.py），写在页面上就是第二个所有者。
         守卫：frontend/scripts/check-dist.mjs 的 FORBIDDEN_STALE_CLAIM（源与产物两侧都扫）。 -->
    <p class="auth__fine">
      本系统<strong>不做</strong>口令找回 / 图形验证码 / OAuth。
      忘了口令要找教务干事把 <code class="data">password_hash</code> 置回
      <code class="data">NULL</code>（逐字局限见 spec §1.2 与 §13）。
      ⚠️ 口令<strong>连错多次会被临时锁定</strong>，稍后再试即可；被锁时看到的
      仍然是「口令不正确」（阈值与逐字口径见 spec §13.4.6）。
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
