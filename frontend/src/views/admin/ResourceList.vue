<script setup lang="ts">
/**
 * `views/admin/ResourceList.vue` —— **一个资源的列表 + 新建 + 行内删除**（`/admin/:resource`）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 它是 23 个资源**共用**的那一个组件（计划 Task 4 逐字）
 * ---------------------------------------------------------------------------
 * 「渲染哪几列」「有没有写按钮」「删除是哪一档策略」全部来自
 * `catalog/resources.ts` 的那一行，本页**一个资源名都没写死**。
 * 手写 23 套的失效形态不是「代码长」，而是 23 份互相不一致的分页/错误/空态行为。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 写按钮一律「**不出现**」，不是「禁用」（计划约束第 20 条）
 * ---------------------------------------------------------------------------
 * 三档，每档一个 `v-if`，**没有一处 `:disabled`**：
 *  1. `!entry.writable`（14 个只读资源）→ 新建 / 删除**都不渲染**，
 *     并把 `readOnlyReason` 摊开在页面上（那是它们的唯一住址，本页不抄第二份）；
 *  2. `!entry.hasDeleteEndpoint`（`on_delete='forbid'` 的 10 个，含可写的 `semesters`）
 *     → **删除**不渲染。⚠️ 后端对这一档根本不注册 DELETE，打过去是
 *     `405 http_405`；一个「禁用」的按钮会让人以为「权限不够」，
 *     而真相是「这个操作不存在」—— 两者要做的下一步完全不同；
 *  3. `!session.isAdmin`（Plan 05A Task 2 之前是「不是教师身份」）→ 写按钮不渲染，
 *     并显示一句「管理台的写操作仅 role=admin 可用」。⚠️ 这一档是 Plan 03 fix 波 1
 *     之后才有的（那时 9 个可写资源的 POST/PATCH/DELETE 全挂 `require_teacher`），
 *     Plan 05A Task 2 把它抬成了 `require_admin`，故判据跟着抬。
 *     ⚠️ 而 Plan 05A Task 3 之后 `/admin/*` 的路由守卫本身就要 `admin`，
 *     故这一档在正常导航下不可达（留着是防御性的）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 表单是**契约驱动**的（`api/contract.ts`）
 * ---------------------------------------------------------------------------
 * 新建表单画哪几格，读的是 `/openapi.json` 里 `*Create` 的 `properties`
 * —— 于是「请求模型不收的列不会出现在表单里」是**自动成立**的。
 * ⚠️ 而这一格今天的实测口径比派单说的那句要窄（**顶回**）：
 * `tests/api/test_crud.py:1510` 的 `_SERVER_FILLED_COLUMNS` **只有一条**
 * —— `{"/api/class-sessions": ("rpe_token",)}`，而 `rpe_token` 连
 * `ClassSessionCreate` 都不在（它属于「服务端生成且是秘密」那一档）。
 * 派单举的 `submitted_at` / `late` 确实是服务端填的，但它们属于
 * `training-logs` / `rpe-records`，那两个资源**不是泛型 CRUD 可写的**
 * （写入走各自的学生头特例端点，请求模型是 `TrainingLogCreate` / `RpeSubmitCreate`）
 * → 它们在管理台里根本没有表单。⚠️ 而 `batch_id` **在** `ClassSessionCreate` 上
 * （可空、缺省 null），故它**会**出现在表单里 —— 契约说收，本页就画。
 *
 * 实测 9 个可写资源的 `*Update` 字段集与 `*Create` **逐字相等**，
 * `*Read` = `*Create` + `id`，且 `*Update` 的 `required` **全是 `[]`**。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 客户端过滤这一格本页**刻意不做**
 * ---------------------------------------------------------------------------
 * 约束第 9 条：泛型 list 只有 `limit` / `offset`，`?rule_id=red` 会被 FastAPI
 * **静默忽略**。本页因此**不提供筛选框** —— 一个「筛了但后端没筛」的界面
 * 比没有筛选更坏（教师端 `/t/alerts` 提供筛选，是因为它把全量拉到客户端再筛，
 * 而管理台的表最大有 840 行，拉全量不是本台的活）。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ApiError } from '../../api/client'
import { assembleBody, formFields, missingRequired, type FormField } from '../../api/contract'
import { createResource, deleteResource, listResource } from '../../api/endpoints'
import SectionHead from '../../components/SectionHead.vue'
import { useAsync } from '../../composables/useAsync'
import { resourceByName } from '../../catalog/resources'
import { cellText, fieldLabelZh, onDeleteZh } from '../../present'
import { useSessionStore } from '../../stores/session'

const route = useRoute()
const session = useSessionStore()

/** 路径参数 `:resource`。⚠️ 同一个组件实例会在 23 个资源之间复用
 *  （路由记录是同一条），故下面那个 `watch` 是承重的。 */
const resourceParam = computed(() => String(route.params.resource ?? ''))

/** 目录里的那一行。⚠️ `undefined` = 「不认识的资源」，渲染成一块说明，不是白屏。 */
const entry = computed(() => resourceByName(resourceParam.value))

/* ------------------------------------------------------------------ 分页 */

/** 一页几行。⚠️ 上界 200 是后端 `deps.Page` 的（`1 <= limit <= 200`），
 *  故这三档是**后端认得的**值，不是随便挑的。 */
const LIMITS = [20, 50, 200] as const
const limit = ref<number>(LIMITS[0])
const offset = ref(0)

const { data, loading, error, settled, reload } = useAsync(async () => {
  const current = entry.value
  if (!current) return null
  return listResource(current.resource, { limit: limit.value, offset: offset.value })
})

/** ⚠️ 换资源 / 换页 → 重读。`useAsync` 的 `load` 是个读 ref 的闭包，
 *  故这里只需要 `reload()`。 */
watch(
  [resourceParam, limit, offset],
  ([resource], [prevResource]) => {
    if (resource !== prevResource) offset.value = 0
    void reload()
  },
)

/** 信封的 4 个键。⚠️ `limit` / `offset` 一律读**服务端生效的那一份**
 *  （约束第 9 条），不要读自己发出去的那一份。 */
const envelope = computed(() => data.value)
const total = computed(() => envelope.value?.total ?? 0)
const shownFrom = computed(() => (total.value === 0 ? 0 : (envelope.value?.offset ?? 0) + 1))
const shownTo = computed(() => (envelope.value?.offset ?? 0) + rows.value.length)

/** 这一页的行。
 *
 *  ⚠️ 那个 `asRecord` 是本页**唯一**一次类型断言：`listResource` 的返回是
 *  23 个 list 项类型的**并集**（`ListItemByResource[ResourceName]`），
 *  而一个「不知道自己在渲染哪个资源」的表格只能按 `Record<string, unknown>` 取值。
 *  强类型的那一份留给具名函数（`listStudents` 之类）与它们的调用方。 */
function asRecord(row: unknown): Record<string, unknown> {
  return row as Record<string, unknown>
}
const rows = computed<Record<string, unknown>[]>(() =>
  (envelope.value?.items ?? []).map(asRecord),
)

/** 表头 = `id` + 目录里挑的那几列（4–6 个；`teachers` 只有 3 列，故给不出 4 个）。 */
const columns = computed<string[]>(() => {
  const current = entry.value
  return current ? ['id', ...current.displayFields] : []
})

function cellOf(row: Record<string, unknown>, column: string): string {
  return cellText(row[column])
}

function idOf(row: Record<string, unknown>): number | null {
  const raw = row.id
  return typeof raw === 'number' && Number.isInteger(raw) ? raw : null
}

/* ------------------------------------------------------------------ 写权限 */

/** 这个资源**能写**（后端注册了 POST/PATCH）。 */
const writable = computed(() => entry.value?.writable === true)
/** 这个资源**有 DELETE 端点**（⚠️ 9 个可写里只有 8 个：`semesters` 是 forbid）。 */
const deletable = computed(() => entry.value?.hasDeleteEndpoint === true)
/** 当前会话能不能写。⚠️ **Plan 05A Task 2 之后是 `role == 'admin'`**（此前是
 *  「有没有教师请求头」）：用户 2026-10-12 逐字裁定「管理员这个角色接管管理台
 *  （23 个资源的增删改查）」，后端 `crud.py` 的 `require_teacher` 因此改成了
 *  `require_admin`，9 个可写资源的 26 个写入操作**仅管理员**可用。
 *  ⚠️ 判据取 `stores/session.ts` 的 `isAdmin`（后端 `GET /api/auth/me` 回的那个
 *  `role`），不取请求头：请求头那一档没有 role，答不出这个问题。 */
const asAdmin = computed(() => session.isAdmin)

/** ⚠️ 三个 `v-if` 就是这三格（见文件头那段）。 */
const showCreate = computed(() => writable.value && asAdmin.value)
const showDelete = computed(() => deletable.value && asAdmin.value)
/** 「可写但当前不是管理员」→ 要说明一句，不能静默地把按钮藏掉。
 *  ⚠️ Plan 05A Task 3 之后 `/admin/*` 的路由守卫已经要 `admin`，故这一格在正常
 *  导航下**不可达**（它是防御性的：守卫被绕过、或 `me` 回的 role 与会话不一致时，
 *  用户看到的是一句说明而不是一个点了才 403 的按钮）。 */
const needTeacher = computed(() => writable.value && !asAdmin.value)

/* ------------------------------------------------------------------ 新建表单 */

const formOpen = ref(false)
const formFields_ = ref<FormField[]>([])
const formSchema = ref<string | null>(null)
const formValues = ref<Record<string, string>>({})
const formLoading = ref(false)
const formError = ref<string | null>(null)
const busy = ref(false)

/** 就地错误 / 就地成功。⚠️ **不**送进 `ApiErrorBanner` 的常驻位：
 *  一次删除失败属于**某一行**，挂在页面顶端会让人以为整页坏了。
 *  ⚠️ 但内容口径与横幅逐字一致：`code` + `err.meta.hint`（那一句「用户现在该做什么」）
 *  + `err.message` **原文**（`on_delete='restrict'` 那一档后端在 message 里
 *  点名了子表 —— 「还被谁引用」就在那一句里，前端写的任何一句都没它具体）。 */
const actionError = ref<ApiError | null>(null)
const actionOk = ref<string | null>(null)

async function openCreateForm(): Promise<void> {
  const current = entry.value
  if (!current) return
  actionError.value = null
  actionOk.value = null
  formError.value = null
  formLoading.value = true
  formOpen.value = true
  try {
    const spec = await formFields(current.path, current.pkField, 'post')
    formSchema.value = spec.schemaName
    formFields_.value = spec.fields
    // ⚠️ 0 格 = 契约里查不到这个请求体（路径拼错、或后端把它摘了）。
    //    **必须就地说明**：一张只有提交按钮的空表单会被读成「表单坏了」。
    if (spec.fields.length === 0) {
      formError.value = `契约里查不到 POST ${current.path} 的请求体字段（schema = ${spec.schemaName ?? 'null'}）。表单不画了 —— 请先核对 /openapi.json。`
      return
    }
    const initial: Record<string, string> = {}
    for (const field of spec.fields) {
      // ⚠️ **不**替用户填后端的缺省值：留空 = 「这一格不传」= 后端取它自己的 default。
      //    前端替它填一份等于把「缺省值是多少」抄成第二个所有者。
      initial[field.name] = ''
    }
    formValues.value = initial
  } catch (err) {
    formError.value =
      err instanceof ApiError
        ? `读不到这个资源的请求契约（${err.code}）：${err.message}`
        : `读不到 /openapi.json：${err instanceof Error ? err.message : String(err)}`
  } finally {
    formLoading.value = false
  }
}

function closeCreateForm(): void {
  formOpen.value = false
  formFields_.value = []
  formSchema.value = null
  formValues.value = {}
  formError.value = null
}

/** 输入框里的串 → 请求体。**空串 = 这一格不传**（不是 `null`）。 */
function collectBody(): Record<string, unknown> | null {
  const { body, error } = assembleBody(formFields_.value, formValues.value)
  formError.value = error
  return body
}

/** **活的**请求体预览（随输入变）。
 *
 *  ⚠️ 它同时是一个**取证点**：`--dump-dom` 读不到 `<input>` 的当前值
 *  （Vue 设的是 `value` **property**，而它不反映到同名 content attribute 上，
 *  故序列化的 HTML 里永远是 `value=""`）。于是「表单里到底装了什么、
 *  哪些键会进请求体」这件事，只有渲染成**文本**才在 DOM 里留得下痕迹。
 *  ⚠️ 它也真的有用：本表单的规矩是「留空 = 这一格不传 = 后端取缺省值」，
 *  而这条规矩在预览里是**看得见**的（空表单预览出 `{}`）。 */
const bodyPreview = computed<string>(() => {
  // ⚠️ 先分「还差必填」与「填了但解析不出来」两档：空表单刚打开时该说前者，
  //    不该劈头一句「『name』是必填的」（`assembleBody` 只报第一个撞上的错）。
  const missing = missingRequired(formFields_.value, formValues.value)
  if (missing.length > 0) {
    return `（还差 ${missing.length} 格必填：${missing.map(fieldLabelZh).join('、')}）`
  }
  const { body, error } = assembleBody(formFields_.value, formValues.value)
  if (error) return `（${error}）`
  const text = JSON.stringify(body)
  return text === '{}' ? '{} —— 每一格都留空，故一个键都不传（后端一律取它自己的缺省值）' : text
})

async function submitCreate(): Promise<void> {
  const current = entry.value
  if (!current) return
  const body = collectBody()
  if (body === null) return
  busy.value = true
  actionError.value = null
  actionOk.value = null
  try {
    const created = await createResource(current.resource, body)
    const id = typeof created.id === 'number' ? created.id : null
    actionOk.value = `已新建${current.titleZh}${id === null ? '' : ` #${id}`}（POST ${current.path} → 201）。`
    closeCreateForm()
    offset.value = 0
    await reload()
  } catch (err) {
    actionError.value = err instanceof ApiError ? err : null
    if (!(err instanceof ApiError)) console.error('[admin:create]', err)
  } finally {
    busy.value = false
  }
}

/* ------------------------------------------------------------------ 删除 */

/** 正在等第二次点击确认的那一行 id。⚠️ **所有**删除都要二次确认（不只是 cascade）：
 *  一次误点删掉一行真数据的代价，比多点一次大得多。 */
const confirmId = ref<number | null>(null)

/** `on_delete='cascade'` 的那一格要写明**会连带删掉什么**（派单第 3 节逐字要求）。
 *  ⚠️ 实测全库只有 **1** 个 cascade 资源：`class-sessions`。 */
const CASCADE_NOTE: Record<string, string> = {
  'class-sessions':
    '⚠️ 这是全库唯一一处 on_delete=cascade：删掉这节课会**连带删掉**这节课收到的全部课堂快评（rpe_record 的行，DB 侧 ON DELETE CASCADE）。学生的 RPE 趋势图上那几个点会一起消失，且不可恢复。',
}

const cascadeNote = computed(() => {
  const current = entry.value
  if (!current || current.onDelete !== 'cascade') return ''
  return CASCADE_NOTE[current.resource] ?? '这一档是级联删除：连带删掉它的子行，且不可恢复。'
})

function askDelete(id: number | null): void {
  if (id === null) return
  actionError.value = null
  actionOk.value = null
  confirmId.value = confirmId.value === id ? null : id
}

async function doDelete(id: number): Promise<void> {
  const current = entry.value
  if (!current) return
  busy.value = true
  actionError.value = null
  actionOk.value = null
  try {
    await deleteResource(current.resource, id)
    actionOk.value = `已删除${current.titleZh} #${id}（DELETE ${current.path}/${id} → 204，没有响应体）。`
    confirmId.value = null
    // ⚠️ 删掉这一页的最后一行时往回退一页，否则会停在一个空页上。
    if (rows.value.length === 1 && offset.value > 0) {
      offset.value = Math.max(0, offset.value - limit.value)
    } else {
      await reload()
    }
  } catch (err) {
    actionError.value = err instanceof ApiError ? err : null
    if (!(err instanceof ApiError)) console.error('[admin:delete]', err)
  } finally {
    busy.value = false
  }
}

/* ------------------------------------------------------------------ 分页动作 */

function prevPage(): void {
  offset.value = Math.max(0, offset.value - limit.value)
}

function nextPage(): void {
  offset.value += limit.value
}

const canPrev = computed(() => offset.value > 0)
const canNext = computed(() => offset.value + limit.value < total.value)

/* ------------------------------------------------------------------ 空态 */

const isEmpty = computed(() => settled.value && !loading.value && total.value === 0)

/* ------------------------------------------------------------------ 深链接
   ⚠️ `?new=1` 落地就把新建表单打开。
   理由与 `src/dev/identity-url.ts` 的 `adoptFromUrl` 是同一条：一条链接
   （教师发在群里、投屏上的二维码、以及联调脚本的无头浏览器取证）落地时
   **没有人去点那个按钮**。`--dump-dom` 不能交互，故没有这一格，
   「契约驱动的新建表单真的渲染出来了」就拿不到任何 DOM 证据。
   ⚠️ 只在 `showCreate` 为真时生效：只读资源与非管理员会话下它**什么都不做**
   （于是深链接也绕不过「写按钮不出现」那三档）。
   ⚠️ Plan 05A Task 3 之后它**不再**能绕过登录：路由守卫对 `/admin/*` 要
   `role=admin`，未登录的深链接会先被送去 `/login?next=/admin/students?new=1`，
   而 `next` 里带着查询串（`to.fullPath`），故登录后仍然落在这一格上。 */
onMounted(() => {
  if (route.query.new !== undefined && showCreate.value) void openCreateForm()
})
</script>

<template>
  <div class="a-page">
    <!-- ⚠️ 目录里没有这一行：不是白屏、也不是 404 页 -->
    <section v-if="!entry" class="">
      <SectionHead :index="1" level="red" label="UNKNOWN RESOURCE" />
      <div class="a-empty">
        <p class="a-empty__title zh-title">不认识的资源：<code class="data">{{ resourceParam }}</code></p>
        <p class="a-empty__why">
          <code class="data">catalog/resources.ts</code> 的 23 行里没有这一行，
          后端 <code class="data">app/api/routers/catalog.py</code> 的
          <code class="data">RESOURCES</code> 里大概也没有（前端目录与后端清单
          由联调守卫按 <code class="data">/openapi.json</code> 逐行反查对账）。
          ⚠️ 若后端确实新加了一个资源，那就是<strong>前端漏了</strong> —— 加一行目录即可，
          本页与详情页会自动跟上（它们是数据驱动的）。
        </p>
        <RouterLink class="btn" to="/admin">← 回资源目录</RouterLink>
      </div>
    </section>

    <template v-else>
      <!-- ① 页头 -->
      <section class="">
        <SectionHead :index="1" :label="`ADMIN · ${entry.resource}`" />
        <header class="a-head">
          <div>
            <h2 class="zh-title a-head__title">{{ entry.titleZh }}</h2>
            <p class="a-head__path data">
              {{ entry.path }} · pk = {{ entry.pkField }} ·
              on_delete = {{ entry.onDelete }}
            </p>
          </div>
          <div class="a-head__meta">
            <span v-if="entry.writable" class="pill pill--green">可写</span>
            <span v-else class="pill a-pill--neutral">只读</span>
            <span class="pill a-pill--neutral">{{ onDeleteZh(entry.onDelete) }}</span>
            <RouterLink class="btn btn--ghost a-btn--sm" to="/admin">← 目录</RouterLink>
          </div>
        </header>
      </section>

      <!-- ② 口径说明（只读理由 / 没有 DELETE 端点 / 身份 / list 排掉的列） -->
      <section v-if="!entry.writable || !entry.hasDeleteEndpoint || needTeacher || entry.listExclude.length > 0"
               class="">
        <SectionHead :index="2" level="amber" label="WHY" />
        <div class="a-note">
          <template v-if="!entry.writable">
            <span class="a-note__title">这一格为什么没有「新建 / 编辑 / 删除」</span>
            <p>{{ entry.readOnlyReason }}</p>
            <p v-if="entry.onDelete === 'forbid'">
              ⚠️ 它的 <code class="data">on_delete</code> 是
              <code class="data">forbid</code>：<strong>后端根本不注册 DELETE 端点</strong>，
              打过去是 <code class="data">405 http_405</code>。这是管道产物，
              要改请重跑批处理（<code class="data">POST /api/pipeline/run-daily</code>
              按 <code class="data">batch_id</code> 先删后算），不要在运行时改数据库。
            </p>
          </template>

          <!-- ⚠️ 这一档是 `semesters`（全库唯一「可写 + forbid」）：它有新建与编辑，
               而**没有**删除端点。不写明就会有人以为「删除按钮坏了」。 -->
          <template v-else-if="!entry.hasDeleteEndpoint">
            <span class="a-note__title">这一格能新建与编辑，但没有「删除」</span>
            <p>
              <code class="data">on_delete</code> 是 <code class="data">forbid</code> →
              <strong>后端根本不注册 DELETE 端点</strong>，打过去是
              <code class="data">405 http_405</code>。⚠️ 它是全库的<strong>时间轴锚点</strong>：
              9 张表按 <code class="data">semester_id</code> 归组，「这个学期不要了」的
              正确做法是把 <code class="data">is_current</code> 置 false（下面的「编辑」就能做），
              而不是删掉它 —— 删掉会让挂在它下面的每一行都失去归属。
            </p>
          </template>

          <template v-if="needTeacher">
            <span class="a-note__title">要写请用管理员账号</span>
            <p>
              这个资源<strong>可写</strong>，而当前会话是「{{ session.summary }}」。
              后端给 9 个可写资源的 POST / PATCH / DELETE 全挂了
              <code class="data">require_admin</code>（口径见 spec §13.4.4；匿名写 →
              <code class="data">401 unauthenticated</code>，普通教师写 →
              <code class="data">403 forbidden</code>），故本页在非管理员会话下
              <strong>不渲染</strong>写按钮 —— 一个点了才报 403 的按钮比一个不出现的
              按钮更坏。⚠️ 正常导航下你到不了这里：路由守卫对
              <code class="data">/admin/*</code> 就要求 <code class="data">role=admin</code>。
            </p>
          </template>

          <template v-if="entry.listExclude.length > 0">
            <span class="a-note__title">这个列表刻意少几列</span>
            <p>
              列表里<strong>看不到</strong>：
              <code v-for="name in entry.listExclude" :key="name" class="data">{{ name }}</code>
              （共 {{ entry.listExclude.length }} 列）。它们是
              <code class="data">JsonText</code> 的大 JSON 列，后端在 list 端点上
              <code class="data">defer</code> 掉它们以免 N+1
              （那一条口径与全部运行须知见 spec §13）。
              <strong>点进任意一行的详情页能看到全部</strong>
              （read-one 挂 <code class="data">response_model</code>、含这些列）。
            </p>
          </template>
        </div>
      </section>

      <!-- ③ 工具条 + 表格 -->
      <section class="">
        <SectionHead :index="3" label="ROWS" />

        <div class="a-toolbar">
          <div class="a-pager">
            <button class="btn a-btn--sm" type="button" :disabled="!canPrev || loading" @click="prevPage">
              ← 上一页
            </button>
            <button class="btn a-btn--sm" type="button" :disabled="!canNext || loading" @click="nextPage">
              下一页 →
            </button>
            <span class="a-pager__where num">
              {{ loading ? '读取中…' : `${shownFrom}–${shownTo} / 共 ${total} 行` }}
            </span>
            <label class="a-pager__where">
              每页
              <select v-model.number="limit" class="select a-select--inline">
                <option v-for="n in LIMITS" :key="n" :value="n">{{ n }}</option>
              </select>
            </label>
          </div>

          <div class="a-actions">
            <button class="btn a-btn--sm" type="button" :disabled="loading" @click="reload">
              ⟳ 重读
            </button>
            <!-- ⚠️ 只读资源 / 非教师身份：这个按钮**不出现**（不是禁用） -->
            <button v-if="showCreate" class="btn btn--primary a-btn--sm" type="button"
                    :disabled="busy || formOpen" @click="openCreateForm">
              ＋ 新建一行
            </button>
          </div>
        </div>

        <!-- 新建表单（契约驱动） -->
        <div v-if="formOpen" class="a-card a-mt">
          <p class="a-count">
            新建一行 · {{ entry.titleZh }} · 请求体 schema
            <code class="data">{{ formSchema ?? '（读不到）' }}</code>
            · ⚠️ 表单里出现的每一格都来自 <code class="data">/openapi.json</code> 的
            <code class="data">{{ formSchema ?? '*Create' }}</code>，一格不多一格不少：
            请求模型不收的列（例如 <code class="data">id</code>，以及
            <code class="data">class-sessions</code> 的口令
            <code class="data">rpe_token</code>）<strong>不会</strong>出现在这里。
            留空 = 「这一格不传」= 后端取它自己的缺省值。
          </p>

          <p v-if="formLoading" class="a-count">正在读契约…</p>
          <p v-else-if="formError" class="a-form__hint">{{ formError }}</p>

          <form v-else class="a-form a-mt" @submit.prevent="submitCreate">
            <div v-for="field in formFields_" :key="field.name" class="field"
                 :class="{ 'field--wide': field.kind === 'json' }">
              <label class="field__label" :for="`new-${field.name}`">
                {{ fieldLabelZh(field.name) }}
                <span v-if="field.required" class="a-form__req">＊必填</span>
              </label>

              <select v-if="field.kind === 'boolean'" class="select" :id="`new-${field.name}`"
                      v-model="formValues[field.name]">
                <option value="">（不传 · 用后端缺省{{ field.hasDefault ? ` ${cellText(field.defaultValue)}` : '' }}）</option>
                <option value="true">是</option>
                <option value="false">否</option>
              </select>
              <textarea v-else-if="field.kind === 'json'" class="a-textarea"
                        :id="`new-${field.name}`" v-model="formValues[field.name]"
                        placeholder='{"…": "…"}'></textarea>
              <input v-else class="input" :id="`new-${field.name}`"
                     :type="field.kind === 'date' ? 'date' : field.kind === 'datetime' ? 'datetime-local' : 'text'"
                     v-model="formValues[field.name]" />

              <span class="a-form__hint">
                <code class="data">{{ field.name }}</code> · {{ field.kind }}
                <template v-if="field.nullable"> · 可空（填 <code class="data">__null__</code> 显式置空）</template>
                <template v-if="field.hasDefault"> · 后端缺省 {{ cellText(field.defaultValue) }}</template>
              </span>
            </div>

            <p class="a-form__preview">
              <span class="caps">将提交的请求体</span>
              <code class="data">{{ bodyPreview }}</code>
            </p>

            <div class="a-form__actions">
              <button class="btn btn--primary a-btn--sm" type="submit" :disabled="busy">
                {{ busy ? '提交中…' : `提交 POST ${entry.path}` }}
              </button>
              <button class="btn btn--ghost a-btn--sm" type="button" @click="closeCreateForm">取消</button>
            </div>
          </form>
        </div>

        <!-- 就地错误 / 成功 -->
        <div v-if="actionError" class="a-alert" role="alert">
          <span class="a-alert__bar" aria-hidden="true"></span>
          <div class="a-alert__body">
            <span class="a-alert__code data">
              {{ actionError.code }} · {{ actionError.status }} · {{ actionError.request }}
            </span>
            <span class="a-alert__hint">{{ actionError.meta.hint }}</span>
            <!-- ⚠️ message 原样显示：restrict 那一档后端在里面点名了子表 -->
            <span class="a-alert__message">{{ actionError.message }}</span>
          </div>
        </div>
        <div v-else-if="actionOk" class="a-alert a-alert--ok" role="status">
          <span class="a-alert__bar" aria-hidden="true"></span>
          <div class="a-alert__body">
            <span class="a-alert__code">✓ {{ actionOk }}</span>
          </div>
        </div>

        <!-- 空态 -->
        <div v-if="isEmpty" class="a-empty a-mt">
          <p class="a-empty__title zh-title">这一张表今天是 0 行</p>
          <p class="a-empty__why">
            {{ entry.emptyNote ?? '演示库上没有这一格的行。若它本该有数据，请先重跑 backend/scripts/demo.ps1 复原演示库。' }}
          </p>
        </div>

        <!-- 表格 -->
        <div v-else class="a-scroll a-mt">
          <table class="data-table a-table">
            <thead>
              <tr>
                <th v-for="column in columns" :key="column" scope="col">
                  {{ fieldLabelZh(column) }}
                  <code class="a-slug data">{{ column }}</code>
                </th>
                <th v-if="showDelete" scope="col">操作</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="row in rows" :key="idOf(row) ?? cellText(row.id)">
                <tr>
                  <td v-for="column in columns" :key="column"
                      :class="{ 'a-cell--wrap': column === 'suggestion' || column === 'schedule_text' }">
                    <RouterLink v-if="column === 'id'" class="a-rowlink"
                                :to="`/admin/${entry.resource}/${idOf(row)}`">
                      {{ cellOf(row, column) }}
                    </RouterLink>
                    <template v-else>{{ cellOf(row, column) }}</template>
                  </td>
                  <td v-if="showDelete">
                    <button class="btn a-btn--sm a-btn--danger" type="button"
                            :disabled="busy" @click="askDelete(Number(idOf(row)))">
                      删除
                    </button>
                  </td>
                </tr>

                <!-- 二次确认：单独一行，跨满整表宽 -->
                <tr v-if="confirmId !== null && idOf(row) === confirmId">
                  <td :colspan="columns.length + (showDelete ? 1 : 0)">
                    <div class="a-confirm">
                      <p class="a-confirm__text">
                        确认删除{{ entry.titleZh }} <strong>#{{ confirmId }}</strong>？
                        <code class="data">DELETE {{ entry.path }}/{{ confirmId }}</code>
                        → 成功是 <strong>204</strong>（没有响应体），不可撤销。
                      </p>
                      <p v-if="cascadeNote" class="a-confirm__text">{{ cascadeNote }}</p>
                      <p v-else-if="entry.onDelete === 'restrict'" class="a-confirm__text">
                        ⚠️ 这一档是 <code class="data">restrict</code>：若还有子表指着这一行，
                        后端会回 <strong>409 <code class="data">integrity_conflict</code></strong>，
                        并在 <code class="data">message</code> 里点名是哪一张表
                        （下面会原样显示那一句）。
                      </p>
                      <span class="a-actions">
                        <button class="btn btn--primary a-btn--sm a-btn--danger" type="button"
                                :disabled="busy" @click="doDelete(Number(confirmId))">
                          {{ busy ? '删除中…' : '确认删除' }}
                        </button>
                        <button class="btn btn--ghost a-btn--sm" type="button"
                                @click="confirmId = null">
                          取消
                        </button>
                      </span>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>

        <!-- 读取失败：`useAsync` 已经把它送进 `ApiErrorBanner` 的常驻位，
             这里只留一句就地说明，不重复整份错误体。 -->
        <p v-if="error" class="a-count a-mt">
          列表读不到（详见页面上方的错误横幅）。
        </p>
      </section>
    </template>
  </div>
</template>
