<script setup lang="ts">
/**
 * `views/admin/AuditLogList.vue` —— **审计留痕（只读）**（`/admin/audit-logs`）。
 *
 * ---------------------------------------------------------------------------
 * 它渲染什么（Plan 06 Task 9 = 计划 §9 第 3 条 = Task 5 的后置部分）
 * ---------------------------------------------------------------------------
 * Task 5 落地了 `audit_log` 那一张表（28 张里的那一张）与 `GET /api/audit-logs`
 * （**仅 `role='admin'`**：管理员 200 / 普通教师 403 / 学生 403 / 匿名 401），
 * 但**管理台没有页面** → 运维今天只能 `curl`。本页把那一格补上。
 *
 * ⚠️⚠️ **只用既有端点，一个新端点都不加**（派单 §2 第 2 条）。分页与两个过滤参数
 * 一律照端点的**真实签名**写（实测）：
 *
 *   `limit`  ∈ [1, 200]，缺省 **50**     `offset` ≥ 0，缺省 **0**
 *   `subject_kind` ∈ `anonymous` / `student` / `teacher`
 *   `method`       ∈ `POST` / `PATCH` / `DELETE`（⚠️ 后端**先归一化成大写**再校验，
 *                  故 `?method=post` 是 **200** 不是 422）
 *
 * ⚠️ **一个不在取值域里的值是 422 `unprocessable_value`**（后端会点名合法值），
 * 而不是「静默返回 0 行」—— 后者会让运维以为「今天没有删除操作」。
 * 故本页的两个下拉**只列出合法值**（唯一所有者是 `types.ts` 的
 * `AUDIT_SUBJECT_KINDS` / `AUDITED_METHODS`，它们各自指向后端那一个常量），
 * 于是「敲一个 422 进去」在本页**做不到**。
 *
 * ---------------------------------------------------------------------------
 * ⚠️⚠️ 九列，一列不多（隐私那一格的验收面）
 * ---------------------------------------------------------------------------
 * `AuditLogRead` 的 **9** 格逐格画一列，**一个都不加**：
 * `id` / `at` / `subject_kind` / `subject_id` / `staff_no` / `method` / `path` /
 * `status` / `target`。⚠️ 九格**全是标量**，而**一个请求体都不落** ——
 * 那不是一句承诺，是一条**结构性质**：那张表的 9 列里根本没有能装请求体的位置
 * （后端 `app/db/models/audit.py` 的模块 docstring 第一节），守卫是
 * `tests/api/test_audit_api.py` 的
 * `test_a_login_with_a_password_leaves_no_trace_of_that_password_in_the_audit_row`
 * （它**真的发一次带口令的 login**，然后把落库那一行的全部 9 列逐列扫一遍，
 * 断言口令串与出生日期串一个都不出现）。
 *
 * ⚠️⚠️ **本页不得成为绕过那条守卫的路**（派单 §2 第 5 条）：页面上只画端点已经给的
 * 那 9 格，**不**去别处补任何一格。于是「审计页上看不到口令」与
 * 「审计行里没有口令」是同一件事的两个说法，而前者由 `smoke.mjs` 第 14 步的
 * DOM 取证钉（needle 命中 + 无重叠 + 无溢出），后者由上面那条后端守卫钉。
 *
 * ⚠️⚠️ 两处**刻意不做**（都是「凭空加一列就是凭空撒一句关于这张表的谎」）：
 *  1. **没有「请求体」列**，也没有耗时 / ip / user-agent —— 它们**不在这个契约里**；
 *  2. **不把 `subject_id` 回查名册补成人名 / 学号**。⚠️ 派单写的是「身份（工号/学号）」，
 *     而实测这一格是**代理键**（`student.id` 或 `teacher.id`，1–60 的小整数），
 *     不是学号；`staff_no` 才是工号（且**只对教职有值**）。
 *     ⚠️ 不回查是后端 `AuditLogRead` 的既有裁定，理由逐字住在它的 docstring 里：
 *     鉴权失败时**根本不知道**是谁（那一档 `subject_kind='anonymous'`、两格皆 `null`），
 *     而一个事后补出来的 id 会把「撞门的人」伪装成「在册的人」。
 *     故本页把这一列**原样**画成代理键，并在下面第 02 块把这件事写明。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 权限：只有 admin 能进（**复用既有那一套路由守卫，不写第二套**）
 * ---------------------------------------------------------------------------
 * `router/index.ts` 上这一条路由的 `meta.requires` 是字面的 `'admin'`，
 * 与另外三条 `/admin/*` **逐字同形**；判据是 `stores/session.ts` 的 `satisfies`
 * （`kind === 'teacher' && role === 'admin'`），落空时守卫把用户送到**他自己的**首页
 * 并写一句 `session.notice`（计划 §4.2 逐字要求「不要只显示空白」）。
 * ⚠️ 于是本页**不写任何角色判断**：一个普通教师点进来会被弹回 `/t/dashboard`，
 * 根本到不了这里的 `setup()`。⚠️ 而**后端那道闸门照旧在**（`require_admin`）——
 * 前端守卫挡的是「教用户点一个必然失败的按钮」，不是安全边界。
 * ⚠️ 守卫是 `smoke.mjs` 第 14 步的两拍（admin 档渲染出九列 / 非 admin 档被弹走）。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 排序与信封：与泛型 list **同形而不同序**
 * ---------------------------------------------------------------------------
 * 四个信封键逐字同形（`items` / `total` / `limit` / `offset`），`total` 是**过滤后**的
 * 计数（与 `items` 走同一个 `WHERE`），故下面那个分页器不会给出一个翻不到的页数。
 * ⚠️ 而 `items` 按 **`id DESC`**（最新在前），与泛型 list 的 `ORDER BY id` 升序**相反**
 * —— 审计要的是「最近谁动了什么」。⚠️ 本页因此**不再排一次序**：顺序是后端给的，
 * 前端重排就是第二个所有者。
 *
 * ⚠️ **本端点自己不产生审计行**（它是 GET，而 `should_record` 只认三个写方法）：
 * 否则审计页会自己喂自己（每翻一页多一行「有人翻了审计」），而那张表是
 * **单调增长、没有清理任务**的。⚠️ 代价：「谁看过审计」今天查不到，已登记为待清扫。
 *
 * ⚠️ **本页没有任何写操作**（不可改写是审计的第一条性质）：没有「新建」、
 * 没有「编辑」、没有「删除」，故 `AuditLog` 也**不在** `catalog/resources.ts`
 * 那 23 行里（它是特例端点，同 `/api/health` 那一族）。
 */
import { computed, ref, watch } from 'vue'

import { listAuditLogs } from '../../api/endpoints'
import type { AuditLogItem, AuditMethod, AuditSubjectKind } from '../../api/types'
import { AUDITED_METHODS, AUDIT_SUBJECT_KINDS } from '../../api/types'
import SectionHead from '../../components/SectionHead.vue'
import { useAsync } from '../../composables/useAsync'
import { UNKNOWN, stampSecondsOf, text } from '../../present'

/* ------------------------------------------------------------------ 九列
   ⚠️ **字面清单**（硬规矩 #35）：不从响应体反推。两侧同源的话，「后端给那张表加了
   一列 `body`」会让本清单自动多一列、于是隐私守卫**仍然绿** —— 而那正是它要抓的失效。
   ⚠️ 而「一格不多、一格不少」由下面 `cellOf` 的那个 `switch` 在**编译期**钉住：
   它的形参是 `ColumnKey`（= 这九个键的并集）而返回类型是 `string`，
   故少写一个 `case` 会让 `vue-tsc -b` 当场红（TS 的穷尽性检查），
   多写一个不存在的键则过不了 `key: keyof AuditLogItem`。 */
/* ⚠️⚠️ `wrap: true` 那三列是 **Plan 06 Task 12（C1）** 加的，而它是**承重**的：
   那三列装的正是**客户端可控**的原文（`path` = 请求路径、`target` = 路径段原文、
   `staff_no` = 开发档那个请求头），后端 `app/db/width.py` 把它们按声明宽度截到
   **256 / 64 / 32** 个字符（并留下 `…[cut]` 或 `<over:N>` 的标记）。
   ⚠️ 而 256 个字符里**没有一个空格**（一条 `/aaa…` 的探测路径），
   `.a-table td` 那句 `white-space: nowrap` + `max-width: 340px` 在**自动表格布局**下
   夹不住它 —— 实测（`smoke.mjs` 第 14 步的布局守卫，真扣一条 400 字符的路径进库）：
   那一格 `scrollWidth 1927 / clientWidth 413`，而且它的矩形**压到了**同一行的
   「状态码」与「对象」两格上（`ratio 1` = 完全覆盖）。
   ⚠️ 修法不是新写一条 CSS，而是复用既有的 `.a-cell--wrap`
   （`styles/admin.css`：`white-space: normal; word-break: break-word`，
   它本来就是给 `body` / `schedule_text` / `suggestion` 那三族长文本列用的）
   ⇒ **一条新 CSS 都没加、一个色值裸值都没引**（`npm run check:tokens` 一格未退）。
   ⚠️ 而「审计页读得回来、且读回来不撑破版面」正是 C1 端到端取证的第 ④ 格。 */
const COLUMNS = [
  { key: 'id', label: '行 id', wrap: false },
  { key: 'at', label: '时刻', wrap: false },
  { key: 'subject_kind', label: '身份类型', wrap: false },
  { key: 'subject_id', label: '身份 id', wrap: false },
  { key: 'staff_no', label: '工号', wrap: true },
  { key: 'method', label: '方法', wrap: false },
  { key: 'path', label: '路径', wrap: true },
  { key: 'status', label: '状态码', wrap: false },
  { key: 'target', label: '对象', wrap: true },
  /* ⚠️ `wrap` 逐格**显式写出**（`false` 也写）：`as const` 之下少写一格的失效是
     **编译期**的（`vue-tsc` 报 `Property 'wrap' does not exist`，本机实测踩过），
     而写全之后「哪三列会折行」是一件一眼看完的事。 */
] as const satisfies readonly { key: keyof AuditLogItem; label: string; wrap: boolean }[]

type ColumnKey = (typeof COLUMNS)[number]['key']

/** ⚠️⚠️ **编译期的「九列恰好是 `AuditLogRead` 的九格」**（两个方向都查）：
 *  少一列 → 上面 `cellOf` 的 `switch` 返回类型带上 `undefined`、与声明的 `string`
 *  冲突；多一列 / 写错一个键 → 过不了 `satisfies` 里的 `key: keyof AuditLogItem`。
 *  ⚠️ 本行是第三道（也是唯一一道**点名**这件事的）：`_NineColumns` 若不是 `true`
 *  就无从赋值，`vue-tsc -b` 当场红。 */
type _NineColumns = ColumnKey extends keyof AuditLogItem
  ? keyof AuditLogItem extends ColumnKey
    ? true
    : never
  : never
const _columnsAreExactlyTheNineFields: _NineColumns = true
void _columnsAreExactlyTheNineFields

/** `subject_kind` 的三档中文。⚠️ 取值域的唯一所有者是后端
 *  `AuditLog.SUBJECT_KINDS`（`types.ts` 的 `AUDIT_SUBJECT_KINDS` 指着它），
 *  故本表**只负责翻译**、不负责定义；⚠️ 不认识的值原样显示
 *  （把一个新出现的身份类型画成「匿名」等于把「我不知道」讲成「没人」）。 */
const SUBJECT_KIND_ZH: Record<string, string> = {
  anonymous: '匿名',
  student: '学生',
  teacher: '教职',
}

function subjectKindZh(value: string): string {
  return SUBJECT_KIND_ZH[value] ?? value
}

/** 状态码那一格的语义色。⚠️ **不写色值**：折成 `base.css` 既有的三个 `.pill--*`
 *  类名（色值的唯一住址是 `styles/tokens.css`，守卫是 `npm run check:tokens`）。
 *  ⚠️ 4xx 一律 `amber` 而不是 `red`：审计里 4xx 是**常态**（一次口令敲错就是一条 401），
 *  把它画成红的会让整页看起来像出了事；⚠️ 5xx 才是 `red`。 */
function statusPillOf(status: number): string {
  if (status >= 500) return 'pill pill--red num'
  if (status >= 400) return 'pill pill--amber num'
  return 'pill pill--green num'
}

/** 九列各自的取值口径。⚠️ `switch` **不写 `default`**：那是刻意的，
 *  少一个 `case` 会让返回类型带上 `undefined`、与声明的 `string` 冲突 → 编译期红。 */
function cellOf(row: AuditLogItem, key: ColumnKey): string {
  switch (key) {
    case 'id':
      return String(row.id)
    case 'at':
      // ⚠️ **秒级**、且**不做任何时区换算**（`at` 是 naive 本地时刻，逐字理由见
      //    `present.ts` 的 `stampSecondsOf`）。
      return stampSecondsOf(row.at)
    case 'subject_kind':
      return subjectKindZh(row.subject_kind)
    case 'subject_id':
      // ⚠️ **代理键**，不是学号（`anonymous` 那一档是 `null` → 「—」，不是 0）
      return row.subject_id === null ? UNKNOWN : String(row.subject_id)
    case 'staff_no':
      return text(row.staff_no)
    case 'method':
      return row.method
    case 'path':
      return row.path
    case 'status':
      return String(row.status)
    case 'target':
      return text(row.target)
  }
}

/* ------------------------------------------------------------------ 分页 + 过滤 */

/** 一页几行。⚠️ 上界 200 是后端 `deps.Page` 的（`1 <= limit <= 200`），
 *  故这三档是**后端认得的**值，不是随便挑的（与 `ResourceList.vue` 逐字同一组）。 */
const LIMITS = [20, 50, 200] as const
const limit = ref<number>(LIMITS[1])
const offset = ref(0)
const subjectKind = ref<AuditSubjectKind | null>(null)
const method = ref<AuditMethod | null>(null)

const { data, loading, error, settled, reload } = useAsync(() =>
  listAuditLogs({
    limit: limit.value,
    offset: offset.value,
    subjectKind: subjectKind.value,
    method: method.value,
  }),
)

/* ⚠️ 四个 ref 一起看：一次「换过滤」会把 `offset` 归零（下面那两个 `@change`），
   于是同一 tick 里有两个 dep 变了 —— Vue 的 watcher 按 tick 合并，故只重读一次。 */
watch([subjectKind, method, limit, offset], () => {
  void reload()
})

const rows = computed(() => data.value?.items ?? [])
const total = computed(() => data.value?.total ?? 0)
/* ⚠️ 一律读**响应体里**的 `offset`（后端实际用的那一个），不读自己发出去的 ref
   （约束第 9 条同一条口径）。 */
const shownFrom = computed(() => (total.value === 0 ? 0 : (data.value?.offset ?? 0) + 1))
const shownTo = computed(() => (data.value?.offset ?? 0) + rows.value.length)
const canPrev = computed(() => offset.value > 0)
const canNext = computed(() => offset.value + limit.value < total.value)
const isEmpty = computed(() => settled.value && !loading.value && total.value === 0)

/** 换过滤 / 换每页行数 → 回到第一页（否则「第 3 页」在一个只剩 1 页的结果集上是空的，
 *  而空态会说「今天没有删除操作」——那是一句由分页造成的假话）。 */
function resetPage(): void {
  offset.value = 0
}

function prevPage(): void {
  offset.value = Math.max(0, offset.value - limit.value)
}

function nextPage(): void {
  offset.value += limit.value
}
</script>

<template>
  <div class="a-page">
    <!-- ① 抬头 -->
    <section class="">
      <SectionHead :index="1" label="ADMIN · AUDIT TRAIL" />
      <header class="a-head">
        <div>
          <h2 class="zh-title a-head__title">审计留痕</h2>
          <p class="a-head__path data">/admin/audit-logs · GET /api/audit-logs</p>
        </div>
        <div class="a-head__meta">
          <span class="pill a-pill--neutral">共 {{ total }} 行</span>
          <span class="pill pill--green">仅 role=admin 可读</span>
          <span class="pill a-pill--solid">只读 · 无写操作</span>
        </div>
      </header>
    </section>

    <!-- ② 口径：这张表记什么、不记什么 -->
    <section class="">
      <SectionHead :index="2" level="amber" label="WHAT IT RECORDS" />
      <div class="a-note">
        <span class="a-note__title">四个口径（一律是后端的既有裁定，本页只把它摊开）</span>
        <p>
          <strong>只记三个写方法</strong>：<code class="data">POST</code> /
          <code class="data">PATCH</code> / <code class="data">DELETE</code>
          （唯一所有者是后端 <code class="data">app/api/audit.py</code> 的
          <code class="data">AUDITED_METHODS</code>）。⚠️ <strong>GET 一律不记</strong>，
          故「谁读过什么」查不到，而<strong>翻这一页自己也不会留下行</strong>
          （否则审计页会自己喂自己，而这张表是单调增长、没有清理任务的）。
        </p>
        <p>
          <strong>九格全是标量，一个请求体都不落</strong>：那张表的 9 列里
          <strong>根本没有</strong>能装请求体的位置，故「不记请求体」是一条
          <strong>结构性质</strong>、不是「克制住不写」。⚠️ 于是本页<strong>没有</strong>
          「请求体」列，也<strong>没有</strong>耗时 / ip / user-agent ——
          它们不在这个契约里，凭空加一列就是凭空撒一句关于这张表的谎。
          ⚠️ 后端有一条隐私取证守卫真的发一次带口令的 login、然后扫落库那一行的全部 9 列。
        </p>
        <p>
          <strong>「身份」那三格怎么读</strong>：<code class="data">subject_kind</code> 是
          三档之一（<code class="data">anonymous</code> = <strong>谁在撞门</strong>，
          鉴权失败的行全在这一档）；<code class="data">subject_id</code> 是
          <strong>代理键</strong>（<code class="data">student.id</code> 或
          <code class="data">teacher.id</code>，⚠️ <strong>不是学号</strong>）；
          <code class="data">staff_no</code> 是工号、且<strong>只对教职有值</strong>。
          ⚠️ 本页<strong>刻意不回查名册</strong>把代理键补成人名：鉴权失败时根本不知道是谁，
          而一个事后补出来的 id 会把「撞门的人」伪装成「在册的人」
          （后端 <code class="data">AuditLogRead</code> 的 docstring 逐字写了这条裁定）。
        </p>
        <p>
          <strong>时刻是 naive 本地时刻</strong>：<code class="data">at</code> 序列化成
          <code class="data">2025-10-12T09:30:00</code> 而<strong>不带</strong>
          <code class="data">Z</code> 后缀，故本页<strong>只切串、不建 Date</strong>
          （任何时区换算都会差 8 小时）。⚠️ 顺序是 <code class="data">id DESC</code>
          （最新在前），与泛型 list 的升序<strong>相反</strong>，而本页
          <strong>不再排一次序</strong>。
        </p>
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
            <select v-model.number="limit" class="select a-select--inline" @change="resetPage">
              <option v-for="n in LIMITS" :key="n" :value="n">{{ n }}</option>
            </select>
          </label>
          <!-- ⚠️ 两个过滤参数**就是端点那两个**（后端刻意没有第三个：没有 `since` /
               `until`、也没有 `path` 前缀匹配，逐字理由见 `AuditLogFilter` 的 docstring）。
               ⚠️ 下拉只列合法值，故「敲一个 422 进去」在本页做不到。 -->
          <label class="a-pager__where">
            身份类型
            <select v-model="subjectKind" class="select a-select--inline" @change="resetPage">
              <option :value="null">（不过滤）</option>
              <option v-for="value in Object.values(AUDIT_SUBJECT_KINDS)" :key="value" :value="value">
                {{ subjectKindZh(value) }} · {{ value }}
              </option>
            </select>
          </label>
          <label class="a-pager__where">
            方法
            <select v-model="method" class="select a-select--inline" @change="resetPage">
              <option :value="null">（不过滤）</option>
              <option v-for="value in Object.values(AUDITED_METHODS)" :key="value" :value="value">
                {{ value }}
              </option>
            </select>
          </label>
        </div>

        <div class="a-actions">
          <button class="btn a-btn--sm" type="button" :disabled="loading" @click="reload">
            ⟳ 重读
          </button>
        </div>
      </div>

      <!-- 空态 -->
      <div v-if="isEmpty" class="a-empty a-mt">
        <p class="a-empty__title zh-title">这一张表今天是 0 行</p>
        <p class="a-empty__why">
          <template v-if="subjectKind !== null || method !== null">
            ⚠️ 而这一格<strong>可能是过滤造成的</strong>：当前过滤是
            <code class="data">subject_kind={{ subjectKind ?? '（不限）' }}</code> ·
            <code class="data">method={{ method ?? '（不限）' }}</code>。
            把两个下拉都调回「（不过滤）」再看一次 —— 否则「今天没有删除操作」
            这句结论是由一个还挂着的过滤给出的。
          </template>
          <template v-else>
            演示库刚复原时它就是 0 行（<code class="data">demo.ps1</code> 灌数据走的是
            <strong>进程内</strong>调用，不经过 HTTP，故不产生审计行）。
            在前端登录一次、或处置一条预警，这一页立刻就有行。
          </template>
        </p>
      </div>

      <!-- 表格 -->
      <div v-else class="a-scroll a-mt">
        <table class="data-table a-table">
          <thead>
            <tr>
              <th v-for="column in COLUMNS" :key="column.key" scope="col">
                {{ column.label }}
                <code class="a-slug data">{{ column.key }}</code>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.id">
              <td
                v-for="column in COLUMNS"
                :key="column.key"
                :class="{ 'a-cell--wrap': column.wrap }"
              >
                <span v-if="column.key === 'subject_kind'" class="pill a-pill--neutral">
                  {{ cellOf(row, column.key) }}
                </span>
                <span v-else-if="column.key === 'method'" class="pill a-pill--solid data">
                  {{ cellOf(row, column.key) }}
                </span>
                <span v-else-if="column.key === 'status'" :class="statusPillOf(row.status)">
                  {{ cellOf(row, column.key) }}
                </span>
                <template v-else>{{ cellOf(row, column.key) }}</template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 读取失败：`useAsync` 已经把它送进 `ApiErrorBanner` 的常驻位，
           这里只留一句就地说明，不重复整份错误体（与 `ResourceList.vue` 同一条处置）。 -->
      <p v-if="error" class="a-count a-mt">
        审计行读不到（详见页面上方的错误横幅）。⚠️ 本端点<strong>仅 role='admin'</strong>：
        一个普通教师打过去是 <code class="data">403 forbidden</code>，
        而路由守卫本该在进本页之前就把他弹回 <code class="data">/t/dashboard</code>
        —— 故这一档若真的出现在屏上，说明会话在页面打开之后变了（例如被登出）。
      </p>

      <p class="a-count a-mt">
        ⚠️ 本页<strong>没有任何写操作</strong>：审计行不可改写是审计的第一条性质，
        后端连 <code class="data">PATCH</code> / <code class="data">DELETE</code>
        都不注册（打过去是 <code class="data">405</code>）。
        ⚠️ 而 <code class="data">audit_log</code> <strong>不是</strong>
        <code class="data">catalog/resources.ts</code> 那 23 个资源之一
        （它是特例端点，同 <code class="data">/api/health</code> 那一族），
        故它<strong>不出现</strong>在 <code class="data">/admin</code> 的资源目录那 23 格里。
      </p>
    </section>
  </div>
</template>
