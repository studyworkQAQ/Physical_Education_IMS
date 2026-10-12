<script setup lang="ts">
/**
 * `views/admin/ResourceDetail.vue` —— **读单条 + 编辑（PATCH）**（`/admin/:resource/:id`）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 它是列表页拿不到的那几列的**唯一入口**
 * ---------------------------------------------------------------------------
 * 8 个资源的 list 响应比 `*Read` 少列（合计 19 列 `JsonText`：后端在 list 端点上
 * `defer` 掉它们以免 N+1，`crud.py:582-585`）。read-one 挂
 * `response_model=schemas.read`，**含全部列** —— 故「这张处方的 `training_package`
 * 长什么样」「这条预警的 `trigger_snapshot` 里有什么」只能在这里看到。
 * 本页因此把 `listExclude` 的那几列**打上标记**（「列表里没有」），
 * 于是「为什么列表页看不到它」这件事在页面上就有答案。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 编辑只送**改动过的那几格**
 * ---------------------------------------------------------------------------
 * PATCH 的语义是「只改传上来的」。本页把表单的当前值与 read-one 的原值逐格对比，
 * 只把**不同的**那些键放进请求体（一个改动都没有时不发请求、就地说明）。
 * 于是 `submitted_at` / `late` / `batch_id` 这类**服务端填的列**根本不会出现在
 * 请求体里 —— 它们本来也不在 `*Update` 上（表单是契约驱动的，见 `api/contract.ts`）。
 *
 * ⚠️ 实测 9 个可写资源的 `*Update` 字段集与 `*Create` **逐字相等**，
 * 且 `*Update` 的 `required` **全是 `[]`**（PATCH 嘛），
 * 故「一张表单同时服务新建与编辑」是安全的，差别只在预填与「只送差集」。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ `ClassSessionRead` 是 **6** 列不是 7 列
 * ---------------------------------------------------------------------------
 * `rpe_token` 已被 Plan 03 收尾的 fix 波 2 从读模型上摘掉（它是本仓第一个与 DB 列
 * **不逐字对齐**的 `*Read`）。故本页在 `class-sessions` 上**看不到口令** ——
 * 教师要口令请去 `/t/dashboard` 或 `/t/alerts`（那里调
 * `GET /api/class-sessions/{id}/rpe-token`，教师头）。本页不做那个特例端点：
 * 管理台是运维视角，它显示的是**库里那一行**，不是「教师课堂上要投屏的东西」。
 */
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ApiError } from '../../api/client'
import { assembleBody, formFields, toInputValue, type FormField } from '../../api/contract'
import { readResource, updateResource } from '../../api/endpoints'
import LaneDivider from '../../components/LaneDivider.vue'
import { useAsync } from '../../composables/useAsync'
import { resourceByName } from '../../catalog/resources'
import { cellText, fieldLabelZh, onDeleteZh } from '../../present'
import { useSessionStore } from '../../stores/session'

const route = useRoute()
const session = useSessionStore()

const resourceParam = computed(() => String(route.params.resource ?? ''))
const entry = computed(() => resourceByName(resourceParam.value))

/** 路径参数 `:id`。⚠️ 不是正整数就**不发请求**（打过去必然是
 *  `422 request_validation_failed`，而那一档的 `loc` 是 `["path", "xxx_id"]`
 *  —— 约束第 4 条逐字说过：那个报错会把下一个人支去查前端表单，真因是 URL）。 */
const idParam = computed(() => String(route.params.id ?? ''))
const id = computed<number | null>(() => {
  const n = Number(idParam.value)
  return Number.isInteger(n) && n > 0 ? n : null
})
const badId = computed(() => id.value === null)

const { data, loading, error, reload } = useAsync(async () => {
  const current = entry.value
  if (!current || id.value === null) return null
  return readResource(current.resource, id.value)
})

/** 这一行的键值对（**顺序 = 后端响应的顺序**，即 DB 列序）。 */
const pairs = computed<Array<[string, unknown]>>(() => {
  const row = data.value
  return row ? Object.entries(row) : []
})

/** 被 list 排掉的那几列（要标记出来）。 */
const excludedSet = computed(() => new Set(entry.value?.listExclude ?? []))

function isObject(value: unknown): boolean {
  return typeof value === 'object' && value !== null
}

function prettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

/* ------------------------------------------------------------------ 编辑 */

const editing = ref(false)
const editFields = ref<FormField[]>([])
const editSchema = ref<string | null>(null)
const editValues = ref<Record<string, string>>({})
const editLoading = ref(false)
const formError = ref<string | null>(null)
const busy = ref(false)

const actionError = ref<ApiError | null>(null)
const actionOk = ref<string | null>(null)

const writable = computed(() => entry.value?.writable === true)
/** ⚠️ **Plan 05A Task 2 之后判据是 `role == 'admin'`**（此前是「有没有教师请求头」）：
 *  后端 `crud.py` 的 `require_teacher` 改成了 `require_admin`，PATCH 仅管理员可用。
 *  取 `stores/session.ts` 的 `isAdmin`（后端 `GET /api/auth/me` 回的那个 `role`），
 *  不取请求头 —— 请求头那一档没有 role，答不出这个问题。 */
const asAdmin = computed(() => session.isAdmin)
/** ⚠️ 按钮**不出现**，不是禁用（约束第 20 条）。 */
const showEdit = computed(() => writable.value && asAdmin.value)
/** ⚠️ Plan 05A Task 3 之后 `/admin/*` 的路由守卫就要 `admin`，故这一格在正常导航下
 *  不可达（防御性留着：守卫被绕过时用户看到一句说明，而不是一个点了才 403 的按钮）。 */
const needTeacher = computed(() => writable.value && !asAdmin.value)

async function enterEdit(): Promise<void> {
  const current = entry.value
  const row = data.value
  if (!current || !row) return
  actionError.value = null
  actionOk.value = null
  formError.value = null
  editLoading.value = true
  editing.value = true
  try {
    const spec = await formFields(current.path, current.pkField, 'patch')
    editSchema.value = spec.schemaName
    editFields.value = spec.fields
    // ⚠️ 0 格 = 契约里查不到 PATCH 的请求体。⚠️ 这一格 Task 4 真踩过：
    //    PATCH 挂在**成员**路径（`/api/x/{pk}`）而不是集合路径上，查错了会
    //    **静默**得到 0 格，而提交按钮照旧渲染 —— 看起来像「表单坏了」。
    if (spec.fields.length === 0) {
      formError.value = `契约里查不到 PATCH ${current.path}/{${current.pkField}} 的请求体字段（schema = ${spec.schemaName ?? 'null'}）。表单不画了 —— 请先核对 /openapi.json。`
      return
    }
    const initial: Record<string, string> = {}
    for (const field of spec.fields) {
      initial[field.name] = toInputValue(field, row[field.name])
    }
    editValues.value = initial
  } catch (err) {
    formError.value =
      err instanceof ApiError
        ? `读不到这个资源的请求契约（${err.code}）：${err.message}`
        : `读不到 /openapi.json：${err instanceof Error ? err.message : String(err)}`
  } finally {
    editLoading.value = false
  }
}

function exitEdit(): void {
  editing.value = false
  editFields.value = []
  editSchema.value = null
  editValues.value = {}
  formError.value = null
}

/** 两个任意值相等吗。⚠️ 对象走 JSON 串比：`toInputValue` 把对象摊成
 *  缩进过的 JSON，`fromInputValue` 再 `parse` 回来，键序不变（`JSON.parse`
 *  保持插入序），故串比是可靠的。 */
function sameValue(a: unknown, b: unknown): boolean {
  if (isObject(a) || isObject(b)) return prettyJson(a) === prettyJson(b)
  return a === b
}

/** 一份「全部非空的表单值」→ **只留下与库里那一行不同**的键。 */
function diffOf(body: Record<string, unknown>): Record<string, unknown> {
  const row = data.value ?? {}
  const patch: Record<string, unknown> = {}
  for (const [name, value] of Object.entries(body)) {
    if (!sameValue(value, row[name])) patch[name] = value
  }
  return patch
}

/** 只收「与原值不同」的那些键。 */
function collectPatch(): Record<string, unknown> | null {
  if (!data.value) return null
  const { body, error } = assembleBody(editFields.value, editValues.value)
  formError.value = error
  return body === null ? null : diffOf(body)
}

/** **活的**差集预览（随输入变）。
 *
 *  ⚠️ 它同时是一个**取证点**：`--dump-dom` 读不到 `<input>` / `<select>` 的当前值
 *  （Vue 设的是 property，`value` 与 `selectedIndex` 都不反映到 content attribute 上，
 *  故序列化的 HTML 里每个输入框都是空的）。于是「表单预填的是不是 read-one 的原值」
 *  这件事，只有渲染成**文本**才在 DOM 里留得下痕迹 —— 刚打开表单时它必须是
 *  `{}`（一格都没改），那就证明预填逐字等于原值。
 *  ⚠️ 它也真的有用：PATCH 只送差集，而「到底会送哪几格」在按下保存之前就看得见。 */
const patchPreview = computed<{ text: string; count: number }>(() => {
  if (!data.value) return { text: '（还没有读到那一行）', count: 0 }
  const { body, error } = assembleBody(editFields.value, editValues.value)
  if (error !== null || body === null) return { text: `（${error ?? '解析不出来'}）`, count: -1 }
  const patch = diffOf(body)
  const keys = Object.keys(patch)
  if (keys.length === 0) {
    return { text: '{} —— 每一格都与库里那一行逐字相同，故不会发请求', count: 0 }
  }
  return { text: JSON.stringify(patch), count: keys.length }
})

async function submitEdit(): Promise<void> {
  const current = entry.value
  const target = id.value
  if (!current || target === null) return
  const patch = collectPatch()
  if (patch === null) return
  if (Object.keys(patch).length === 0) {
    actionOk.value = '没有改动：表单里的每一格都与库里那一行逐字相同，故没有发请求。'
    return
  }
  busy.value = true
  actionError.value = null
  actionOk.value = null
  try {
    await updateResource(current.resource, target, patch)
    actionOk.value = `已保存（PATCH ${current.path}/${target}，只送了 ${Object.keys(patch).length} 格：${Object.keys(patch).join(', ')}）。`
    exitEdit()
    await reload()
  } catch (err) {
    actionError.value = err instanceof ApiError ? err : null
    if (!(err instanceof ApiError)) console.error('[admin:patch]', err)
  } finally {
    busy.value = false
  }
}

/** ⚠️ 换资源 / 换 id 就重读，并把编辑态与就地消息清掉。
 *  放在文件末尾是为了让 `exitEdit` / `actionError` / `actionOk` 都已声明
 *  （回调虽然是惰性的、TDZ 上不会炸，但「先声明后引用」读起来才不用回头找）。 */
watch([resourceParam, idParam], () => {
  exitEdit()
  actionError.value = null
  actionOk.value = null
  void reload()
})

/* ------------------------------------------------------------------ 深链接
   ⚠️ `?edit=1` 落地就把编辑表单打开（预填库里那一行的值）。
   理由与 `ResourceList.vue` 的 `?new=1` 逐字相同：一条链接落地时没有人去点按钮，
   而 `--dump-dom` 不能交互 —— 没有这一格，「契约驱动的编辑表单真的渲染出来了、
   并且预填的是 read-one 的原值」就拿不到任何 DOM 证据。
   ⚠️ 它必须**等 read-one 回来**才能开表单（预填要那一行的值），故挂在 `data` 上；
   ⚠️ 只在 `showEdit` 为真时生效：只读资源与非教师身份下它什么都不做。 */
let autoEdit = route.query.edit !== undefined
watch(data, (row) => {
  if (autoEdit && row && showEdit.value) {
    autoEdit = false
    void enterEdit()
  }
})
</script>

<template>
  <div class="a-page">
    <!-- 目录里没有这一行 -->
    <section v-if="!entry" class="lane-block" :style="{ '--lane-index': 0 }">
      <LaneDivider :index="1" level="red" label="UNKNOWN RESOURCE" />
      <div class="a-empty">
        <p class="a-empty__title zh-title">
          不认识的资源：<code class="data">{{ resourceParam }}</code>
        </p>
        <p class="a-empty__why">
          <code class="data">catalog/resources.ts</code> 的 23 行里没有它。
        </p>
        <RouterLink class="btn" to="/admin">← 回资源目录</RouterLink>
      </div>
    </section>

    <!-- id 不是一个正整数：不发请求 -->
    <section v-else-if="badId" class="lane-block" :style="{ '--lane-index': 0 }">
      <LaneDivider :index="1" level="red" label="BAD ID" />
      <div class="a-empty">
        <p class="a-empty__title zh-title">
          id 不是一个正整数：<code class="data">{{ idParam || '（空）' }}</code>
        </p>
        <p class="a-empty__why">
          本页<strong>没有发请求</strong>。打过去必然是
          <code class="data">422 request_validation_failed</code>，而它的
          <code class="data">loc</code> 会是 <code class="data">["path", "{{ entry.pkField }}"]</code>
          —— 约束第 4 条逐字点过这一档：那句报错会把下一个人支去查表单，
          真因是 URL 里这一段。
        </p>
        <RouterLink class="btn" :to="`/admin/${entry.resource}`">
          ← 回{{ entry.titleZh }}的列表
        </RouterLink>
      </div>
    </section>

    <template v-else>
      <!-- ① 页头 -->
      <section class="lane-block" :style="{ '--lane-index': 0 }">
        <LaneDivider :index="1" :label="`ADMIN · ${entry.resource} · #${id}`" />
        <header class="a-head">
          <div>
            <h2 class="zh-title a-head__title">{{ entry.titleZh }} #{{ id }}</h2>
            <p class="a-head__path data">
              GET {{ entry.path }}/{{ id }} · pk = {{ entry.pkField }} ·
              on_delete = {{ entry.onDelete }}
            </p>
          </div>
          <div class="a-head__meta">
            <span v-if="entry.writable" class="pill pill--green">可写</span>
            <span v-else class="pill a-pill--neutral">只读</span>
            <span class="pill a-pill--neutral">{{ onDeleteZh(entry.onDelete) }}</span>
            <RouterLink class="btn btn--ghost a-btn--sm" :to="`/admin/${entry.resource}`">
              ← 列表
            </RouterLink>
            <RouterLink class="btn btn--ghost a-btn--sm" to="/admin">目录</RouterLink>
            <!-- ⚠️ 只读 / 非教师身份：**不出现** -->
            <button v-if="showEdit && !editing" class="btn btn--primary a-btn--sm" type="button"
                    :disabled="busy || loading || !data" @click="enterEdit">
              ✎ 编辑
            </button>
          </div>
        </header>
      </section>

      <!-- ② 为什么没有编辑按钮 -->
      <section v-if="!entry.writable || needTeacher" class="lane-block" :style="{ '--lane-index': 1 }">
        <LaneDivider :index="2" level="amber" label="WHY NO EDIT" />
        <div class="a-note">
          <template v-if="!entry.writable">
            <span class="a-note__title">这一格为什么没有「编辑」</span>
            <p>{{ entry.readOnlyReason }}</p>
          </template>
          <template v-if="needTeacher">
            <span class="a-note__title">要写请用管理员账号</span>
            <p>
              这个资源<strong>可写</strong>，而当前会话是「{{ session.summary }}」。
              PATCH 挂了 <code class="data">require_admin</code>（Plan 05A Task 2），
              匿名打过去是 <code class="data">401 unauthenticated</code>、
              一个普通教师打过去是 <code class="data">403 forbidden</code>，
              故编辑按钮在非管理员会话下不渲染。⚠️ 正常导航下你到不了这里：
              路由守卫对 <code class="data">/admin/*</code> 就要求
              <code class="data">role=admin</code>。
            </p>
          </template>
        </div>
      </section>

      <!-- ③ 就地错误 / 成功 -->
      <div v-if="actionError" class="a-alert" role="alert">
        <span class="a-alert__bar" aria-hidden="true"></span>
        <div class="a-alert__body">
          <span class="a-alert__code data">
            {{ actionError.code }} · {{ actionError.status }} · {{ actionError.request }}
          </span>
          <span class="a-alert__hint">{{ actionError.meta.hint }}</span>
          <span class="a-alert__message">{{ actionError.message }}</span>
        </div>
      </div>
      <div v-else-if="actionOk" class="a-alert a-alert--ok" role="status">
        <span class="a-alert__bar" aria-hidden="true"></span>
        <div class="a-alert__body">
          <span class="a-alert__code">✓ {{ actionOk }}</span>
        </div>
      </div>

      <!-- ④ 编辑表单（契约驱动，只送差集） -->
      <section v-if="editing" class="lane-block" :style="{ '--lane-index': 2 }">
        <LaneDivider :index="3" label="EDIT" />
        <div class="a-card">
          <p class="a-count">
            编辑 · 请求体 schema <code class="data">{{ editSchema ?? '（读不到）' }}</code>
            · ⚠️ 只把<strong>改动过</strong>的那几格送上去（PATCH 的语义）；
            留空 = 「这一格不传」= 不改。要显式清空一列，填
            <code class="data">__null__</code>。
            <br />
            ⚠️ 而 <code class="data">*Update</code> 的每一格在<strong>请求模型</strong>上都是
            <code class="data">T | None</code>（9 个资源的 <code class="data">required</code>
            实测全是 <code class="data">[]</code>），故 <code class="data">__null__</code>
            对任何一格都送得出去；但 DB 侧 NOT NULL 的列（例如
            <code class="data">start_date</code>）收到 null 会回
            <strong>409 <code class="data">integrity_conflict</code></strong>，
            下面会把后端那一句原样显示出来。
          </p>

          <p v-if="editLoading" class="a-count">正在读契约…</p>
          <p v-else-if="formError" class="a-form__hint">{{ formError }}</p>

          <form v-else class="a-form a-mt" @submit.prevent="submitEdit">
            <div v-for="field in editFields" :key="field.name" class="field"
                 :class="{ 'field--wide': field.kind === 'json' }">
              <label class="field__label" :for="`edit-${field.name}`">
                {{ fieldLabelZh(field.name) }}
              </label>

              <select v-if="field.kind === 'boolean'" class="select" :id="`edit-${field.name}`"
                      v-model="editValues[field.name]">
                <option value="">（不传 · 不改这一格）</option>
                <option value="true">是</option>
                <option value="false">否</option>
              </select>
              <textarea v-else-if="field.kind === 'json'" class="a-textarea"
                        :id="`edit-${field.name}`" v-model="editValues[field.name]"></textarea>
              <input v-else class="input" :id="`edit-${field.name}`"
                     :type="field.kind === 'date' ? 'date' : field.kind === 'datetime' ? 'datetime-local' : 'text'"
                     v-model="editValues[field.name]" />

              <span class="a-form__hint">
                <code class="data">{{ field.name }}</code> · {{ field.kind }} · 留空 = 不改这一格
                · 库里原值 <code class="data">{{ cellText(data?.[field.name]) }}</code>
              </span>
            </div>

            <p class="a-form__preview">
              <span class="caps">将提交的差集（{{ patchPreview.count < 0 ? '解析失败' : `${patchPreview.count} 格` }}）</span>
              <code class="data">{{ patchPreview.text }}</code>
            </p>

            <div class="a-form__actions">
              <button class="btn btn--primary a-btn--sm" type="submit" :disabled="busy">
                {{ busy ? '保存中…' : `保存 PATCH ${entry.path}/${id}` }}
              </button>
              <button class="btn btn--ghost a-btn--sm" type="button" @click="exitEdit">取消</button>
            </div>
          </form>
        </div>
      </section>

      <!-- ⑤ 这一行的全部列 -->
      <section class="lane-block" :style="{ '--lane-index': editing ? 3 : 2 }">
        <LaneDivider :index="editing ? 4 : 3" label="ROW" />
        <div class="a-card">
          <p v-if="loading" class="a-count">读取中…</p>
          <p v-else-if="error" class="a-count">
            这一行读不到（详见页面上方的错误横幅）。
          </p>
          <p v-else-if="!data" class="a-count">还没有读。</p>

          <div v-else class="a-kv">
            <template v-for="[name, value] in pairs" :key="name">
              <span class="a-kv__k">
                {{ fieldLabelZh(name) }}
                <code class="data">{{ name }}</code>
                <span v-if="excludedSet.has(name)" class="a-kv__tag">列表里没有</span>
              </span>
              <pre v-if="isObject(value)" class="a-kv__v a-kv__pre">{{ prettyJson(value) }}</pre>
              <span v-else class="a-kv__v" :class="{ unknown: value === null }">
                {{ cellText(value) }}
              </span>
            </template>
          </div>

          <p v-if="data && entry.listExclude.length > 0" class="a-count a-mt">
            ⚠️ 上面打了「列表里没有」标记的 {{ entry.listExclude.length }} 列是
            <code class="data">JsonText</code> 大列，list 端点刻意
            <code class="data">defer</code> 掉它们（免 N+1），只有本页（read-one）能读到。
          </p>
          <p v-if="data && entry.resource === 'class-sessions'" class="a-count a-mt">
            ⚠️ 本页看不到 <code class="data">rpe_token</code>：它已被从
            <code class="data">ClassSessionRead</code> 上摘掉（本仓第一个与 DB 列不逐字对齐的
            <code class="data">*Read</code>）。教师要口令请去教师端
            （<code class="data">GET /api/class-sessions/{id}/rpe-token</code>，教师头），
            学生一律手输。
          </p>
        </div>
      </section>
    </template>
  </div>
</template>
