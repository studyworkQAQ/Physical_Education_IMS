<script lang="ts">
/**
 * `ApiErrorBanner.vue` —— **按 `code` 分支**显示一条错误。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 按 `code`，不按 `message`（计划 Task 1 第 5 节 / 约束第 8 条）
 * ---------------------------------------------------------------------------
 * 后端 `app/api/errors.py` 的模块 docstring 逐字写着：「``code`` 是给**程序**看的
 * 稳定标识（前端按它分支），``message`` 是给**人**看的（会随措辞调整，不要按它分支）」。
 * 故本组件的分支表键是 code，而 `message` **只作为原文显示**（它是后端点名了
 * 哪张子表、哪一列的那句话，信息量比前端能写的任何一句都大 —— 尤其是
 * `integrity_conflict` 在 `on_delete='restrict'` 那一档）。
 *
 * ⚠️ **有 `default` 分支，未知 code 不静默**：显示 `code` 与 `message` 的原文。
 * 后端 `errors.py:142` 那句 `_CODE_BY_STATUS.get(status, f"http_{status}")` 是
 * **开放的**（加一个新状态码就有一个新 code），静默会让「后端加了一档」
 * 在前端表现为「点了没反应」。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 三档**不是错误**（tone = `info`）
 * ---------------------------------------------------------------------------
 * `no_weekly_report` / `no_active_prescription` / `outside_microcycle` 是
 * 「没有」而不是「坏了」：周报只在周日生成（约束第 19 条）、处方只在五条触发
 * 之一成立时生成。用红色横幅渲染它们会教用户忽略红色横幅 ——
 * 而下一次真正的 `forbidden` 就会被一起忽略掉。
 */
import { computed, shallowRef } from 'vue'

import type { ApiError } from '../api/client'

/** 一条横幅的语气。`info` 的那三档见文件头。 */
export type BannerTone = 'error' | 'info'

/** 一个 code 的分支产物：一句给人看的处置建议 + 语气。 */
interface Branch {
  readonly tone: BannerTone
  readonly advice: string
}

/**
 * 横幅的状态。**模块级单例**（不是 Pinia store）：
 *
 * ⚠️ 为什么不开一个 `stores/errors.ts` —— 计划第 3 节逐字写了 Pinia「只存三样：
 * 当前身份、当前学期/`as_of`、服务端缓存」。一条转瞬即逝的错误提示三样都不是：
 * 它不持久化（刷新就该消失）、不跨页共享（换页要清）、也没有派生状态。
 * 把它做成 store 会让「本前端有几份状态」这个问题多一个假答案。
 *
 * ⚠️ 用 `shallowRef` 而不是 `ref`：`ApiError` 是一个类实例，深度响应化它
 * 会把 `Error` 的内部结构也代理一遍，而本组件只读它的四个只读字段。
 */
const current = shallowRef<ApiError | null>(null)

/**
 * 横幅的**唯一**写入口。
 *
 * 三个调用方：① `main.ts` 的 `app.config.errorHandler`（没人 catch 的 `ApiError`）；
 * ② 各页面自己的 `try/catch`（Task 2–4）；③ `IdentitySwitcher` 拉名单失败那一档。
 * ⚠️ 只留最新的一条：两条并排的红色横幅读不出先后，而「最新的那次点击失败了」
 * 才是用户要的那一句。
 */
export function useApiError() {
  return {
    error: current,
    raise(error: ApiError): void {
      current.value = error
    },
    dismiss(): void {
      current.value = null
    },
  }
}

/**
 * code → 分支表。
 *
 * ⚠️ 键集合与 `api/client.ts` 的 `ERROR_CODES` **同源不同用**：那一份是
 * 「这个 code 是什么意思 + 它对应哪个 HTTP 状态码」（给日志与折叠区用），
 * 这一份是「用户现在该做什么」（给横幅用）。两份刻意分开：把处置建议塞进
 * `client.ts` 会让 HTTP 层知道 UI 的措辞，那是反方向的依赖。
 *
 * ⚠️ 全部 **14** 个具名 code 都在表里（实测清单见 `client.ts:62-171` 与
 * task-1-report.md 第 4 节）。计划约束第 8 条那份 11 个的清单里有 4 个
 * **不存在**（`unknown_teacher` / `unknown_student` / `rpe_already_submitted` /
 * `conflict`），故不在表里 —— 它们落到 `default`。
 */
const BRANCHES: Record<string, Branch> = {
  /* ---- 身份（三个 code，⚠️ 与计划的口径不同）---- */
  unauthenticated: {
    tone: 'error',
    advice: '没有带上身份请求头。请在左上角的身份切换器里选一个身份，然后重试。',
  },
  forbidden: {
    tone: 'error',
    // ⚠️ 三档刻意同形（deps.py 的 require_scope / require_teacher docstring 逐字写了理由：
    //    区分「不在册」与「不是这个人」等于把在册名单告诉调用方）。故这一句要说全三种可能。
    advice:
      '当前身份无权访问这一份数据。三种可能：① 这个学号/工号不在册；② 你不是这份数据的主人；③ 这个教学班/学生不在你本学期任教的范围内。换一个身份再试。',
  },
  not_recipient: {
    tone: 'error',
    advice: '这条消息不是发给当前这个学生的（或它根本不存在 —— 后端刻意让两档同形）。',
  },

  /* ---- 「没有」而不是「坏了」（三档，tone = info）---- */
  no_weekly_report: {
    tone: 'info',
    advice:
      '这个班在那一周还没有周报。周报只在**周日**的批处理里生成，故周中读本周的周报必然落空 —— 先看大屏（它是现算的）。',
  },
  no_active_prescription: {
    tone: 'info',
    advice:
      '这一天没有生效的处方。处方不每天重发，「没有」是常态 —— 等下一次批处理，或让教师在管理台里查这个学生的处方。',
  },
  outside_microcycle: {
    tone: 'info',
    advice: '那一天不在这张处方的微周期有效期内。通常意味着该换处方了（把业务日 as_of 调回区间内可验证）。',
  },

  /* ---- 课堂快评（三个 code）---- */
  rpe_not_opened: {
    tone: 'error',
    advice: '教师还没有发起这节课的课堂快评。教师端点「发起课堂快评」并把口令投屏之后，学生才交得上来。',
  },
  invalid_rpe_token: {
    tone: 'error',
    advice: '口令不对。请照着老师投屏上的那一串重新输入（口令**只能手输**，学生端拿不到它）。',
  },
  alert_not_pending: {
    tone: 'error',
    advice:
      '这条预警已经处置过了，不能再处置一次。⚠️ 再点一次「减量」不是「改成减量」，而是 0.8 × 0.8 = 0.64 —— 要改主意请等下一轮求值。',
  },

  /* ---- 处方 / 训练单 ---- */
  // ⚠️ 与 `no_active_prescription` 是两种提示：那一档是「等批处理」，这一档是「该换处方了」。

  /* ---- 通用五档 ---- */
  not_found: {
    tone: 'error',
    advice: '这一行不存在（或它的 id 打错了）。',
  },
  integrity_conflict: {
    tone: 'error',
    // ⚠️ 这一档的 `message` 是承重的：on_delete='restrict' 时后端在里面点名了子表，
    //    故 advice 只说「怎么办」，「被谁引用」交给下面那段 message 原文。
    advice:
      '与库里已有的一行冲突，或这一行还被别的数据引用着（下面那句话里点名了是哪一张表 / 哪一个约束）。',
  },
  unprocessable_value: {
    tone: 'error',
    advice: '这个值在业务上不成立。后端把具体原因写在下面那句话里（它是原话照发的）。',
  },
  request_validation_failed: {
    tone: 'error',
    advice: '请求参数没通过校验（下面列出的是哪一格）。',
  },
  internal_error: {
    tone: 'error',
    advice: '服务器内部错误。堆栈在后端的日志里、不在响应体里（后端刻意不泄漏）。',
  },
  http_405: {
    tone: 'error',
    advice:
      '这个资源不允许这个操作。23 个资源里 14 个是**刻意只读**的（spec §4.4：体育专家维护的知识资产，改阈值走版本控制与评审，不在运行时改库），它们根本不注册 POST / PATCH / DELETE。',
  },
}

const FALLBACK: Branch = {
  tone: 'error',
  advice: '前端不认识这个错误码。下面显示的是后端回过来的原文。',
}
</script>

<script setup lang="ts">
import { describeCode } from '../api/client'

const { error, dismiss } = useApiError()

const branch = computed<Branch>(() => (error.value ? (BRANCHES[error.value.code] ?? FALLBACK) : FALLBACK))

/** code 的元信息（HTTP 状态码 + `client.ts` 那一句解释）。 */
const meta = computed(() =>
  error.value ? describeCode(error.value.code, error.value.status) : null,
)

/**
 * ⚠️ `request_validation_failed` 且 `loc` 里出现 `path` → **几乎一定是路由顺序或
 * 路径拼错，不是数据问题**（计划约束第 4 条专门点过这一档：那句报错会把下一个人
 * 支去修前端表单）。这一句是给它加的定向提示。
 */
const looksLikePathBug = computed(() => {
  const detail = error.value?.detail
  if (error.value?.code !== 'request_validation_failed' || !Array.isArray(detail)) return false
  return detail.some(
    (entry) => Array.isArray((entry as { loc?: unknown }).loc) && (entry as { loc: unknown[] }).loc[0] === 'path',
  )
})

const detailText = computed(() => {
  const detail = error.value?.detail
  if (detail === null || detail === undefined) return ''
  try {
    return JSON.stringify(detail, null, 2)
  } catch {
    return String(detail)
  }
})
</script>

<template>
  <!-- ⚠️ 常驻位：`v-if` 只关掉内容，**不**关掉这个组件在 App.vue 里的位置。
       它渲染在 masthead 之下、`<main>` 之上，于是错误不会把内容顶下去又顶回来。 -->
  <div
    v-if="error"
    class="banner"
    :class="[`banner--${branch.tone}`, branch.tone === 'info' ? '' : 'banner--loud']"
    role="status"
    :aria-live="branch.tone === 'info' ? 'polite' : 'assertive'"
  >
    <div class="banner__bar" aria-hidden="true"></div>

    <div class="banner__body">
      <div class="banner__head">
        <span class="banner__code data">{{ error.code }}</span>
        <span v-if="meta" class="banner__status num">{{ meta.status }}</span>
        <span class="banner__where data">{{ error.request }}</span>
        <button class="banner__close" type="button" @click="dismiss()">关闭 ✕</button>
      </div>

      <p class="banner__advice">{{ branch.advice }}</p>

      <p v-if="looksLikePathBug" class="banner__hint">
        ⚠️ 校验失败的 <code class="data">loc</code> 里有 <code class="data">path</code>：
        这几乎一定是**路由顺序或路径拼错**，不是表单数据的问题。去查 URL，不要去改输入框。
      </p>

      <!-- ⚠️ message 原样显示：它是后端点名了子表/列名的那一句，比前端能写的任何一句都具体。 -->
      <p class="banner__message">{{ error.message }}</p>

      <details v-if="detailText" class="banner__detail">
        <summary class="caps">detail</summary>
        <pre class="data">{{ detailText }}</pre>
      </details>
    </div>
  </div>
</template>

<style scoped>
/* ⚠️ 这里出现的**尺寸与颜色一律取自 tokens.css**（唯一住址）。
   唯一一处例外是 `.banner__bar` 的高度 —— 它就是分道线的那两个尺寸，故也取自令牌。 */
.banner {
  position: relative;
  display: flex;
  align-items: stretch;
  gap: 0;
  margin-block-end: var(--space-4);
  background: var(--paper-raised);
  border: var(--border-hairline);
  border-inline-start: none;
  box-shadow: var(--shadow-paper);
}

/* 左端那条竖色带 = 分道线母题竖过来用（粗线 3px + 偏移 6px 的细线 1px） */
.banner__bar {
  flex: 0 0 var(--lane-rule-height);
  background:
    linear-gradient(
      to right,
      var(--red-on-paper) 0 var(--lane-thick),
      transparent var(--lane-thick) calc(var(--lane-thick) + var(--lane-offset)),
      var(--track) calc(var(--lane-thick) + var(--lane-offset))
        calc(var(--lane-thick) + var(--lane-offset) + var(--lane-thin))
    );
}

.banner--info .banner__bar {
  background: linear-gradient(to right, var(--moss-on-paper) 0 var(--lane-thick), transparent var(--lane-thick));
}

.banner__body {
  flex: 1 1 auto;
  min-width: 0;
  padding: var(--space-3) var(--space-4);
}

.banner__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2);
  padding-block-end: var(--space-2);
  border-block-end: var(--border-hairline);
}

.banner__code {
  font-weight: 600;
  font-size: var(--fs-small);
  color: var(--red-on-paper);
}

.banner--info .banner__code {
  color: var(--moss-on-paper);
}

.banner__status {
  font-size: var(--fs-small);
  color: var(--ink-soft);
}

.banner__where {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--fs-micro);
  color: var(--ink-faint);
}

.banner__close {
  flex: 0 0 auto;
  font-family: var(--font-display);
  font-weight: var(--fw-display-700);
  font-size: var(--fs-micro);
  letter-spacing: var(--tracking-caps);
  text-transform: uppercase;
  color: var(--ink-soft);
  border: 1px solid var(--rule-hairline);
  border-radius: var(--radius-sharp);
  padding: 2px var(--space-2);
}

.banner__close:hover {
  color: var(--ink);
  border-color: var(--ink);
}

.banner__advice {
  margin-block-start: var(--space-2);
  font-size: var(--fs-body);
  color: var(--ink);
}

.banner__hint {
  margin-block-start: var(--space-2);
  padding: var(--space-2);
  background: var(--amber-wash);
  color: var(--amber-on-paper);
  font-size: var(--fs-small);
}

.banner__message {
  margin-block-start: var(--space-2);
  padding-block-start: var(--space-2);
  border-block-start: var(--border-hairline);
  font-family: var(--font-data);
  font-size: var(--fs-small);
  color: var(--ink-soft);
  white-space: pre-wrap;
  word-break: break-word;
}

.banner__detail {
  margin-block-start: var(--space-2);
}

.banner__detail summary {
  cursor: pointer;
  color: var(--ink-faint);
}

.banner__detail pre {
  margin-block-start: var(--space-2);
  padding: var(--space-2);
  background: var(--paper-sunken);
  font-size: var(--fs-micro);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 深底（教师大屏）上的那一套 */
.surface-ink .banner {
  background: var(--ink-raised);
  border-color: var(--rule-hairline-on-ink);
  box-shadow: none;
}

.surface-ink .banner__bar {
  background: linear-gradient(
    to right,
    var(--red-on-ink) 0 var(--lane-thick),
    transparent var(--lane-thick) calc(var(--lane-thick) + var(--lane-offset)),
    var(--track-on-ink) calc(var(--lane-thick) + var(--lane-offset))
  );
}

.surface-ink .banner--info .banner__bar {
  background: linear-gradient(to right, var(--moss-on-ink) 0 var(--lane-thick), transparent var(--lane-thick));
}

.surface-ink .banner__code {
  color: var(--red-on-ink);
}

.surface-ink .banner__status,
.surface-ink .banner__advice {
  color: var(--paper);
}

.surface-ink .banner__where,
.surface-ink .banner__message {
  color: var(--paper-soft);
}

.surface-ink .banner__head,
.surface-ink .banner__message {
  border-color: var(--rule-hairline-on-ink);
}

.surface-ink .banner__close {
  color: var(--paper-soft);
  border-color: var(--rule-hairline-on-ink);
}

.surface-ink .banner__close:hover {
  color: var(--paper);
  border-color: var(--paper);
}

.surface-ink .banner__detail pre {
  background: var(--ink-sunken);
  color: var(--paper-soft);
}

.surface-ink .banner__hint {
  background: var(--amber-wash-on-ink);
  color: var(--amber-on-ink);
}
</style>
